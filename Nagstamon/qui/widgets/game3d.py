# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2026 Henri Wahl <henri@nagstamon.de> et al.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA

"""Nagstamon FPS Mode – inspired by psDoom.

Monitoring problems are rendered as 3-D billboard targets in a first-person
perspective arena powered by pygame.  Move through the arena with the keyboard,
look around with the mouse, and **left-click** to fire at the problem centred in
your crosshair to acknowledge it.

Controls
--------
* **Mouse**            – look around (pointer captured on click)
* **W / Arrow-Up**     – walk forward
* **S / Arrow-Down**   – walk backward
* **A / Arrow-Left**   – strafe left
* **D / Arrow-Right**  – strafe right
* **Left click**       – shoot / acknowledge the target in the crosshair
* **Escape**           – release mouse; press again to exit

Requires the ``pygame`` package::

    pip install pygame
"""

import math
import random
from dataclasses import dataclass, field
from threading import Thread
from typing import List, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal

# ---------------------------------------------------------------------------
# pygame – optional import; graceful degradation when not installed
# ---------------------------------------------------------------------------
_PYGAME_IMPORT_ERROR: str = ''
try:
    import pygame
    PYGAME_AVAILABLE = True
except Exception as _exc:
    PYGAME_AVAILABLE = False
    _PYGAME_IMPORT_ERROR = str(_exc)

# ---------------------------------------------------------------------------
# Appearance: monitoring status → RGB colour
# ---------------------------------------------------------------------------
_STATUS_COLORS: dict = {
    'DOWN':        (220,  30,  30),
    'UNREACHABLE': (160,  20,  20),
    'DISASTER':    (255,   0,   0),
    'CRITICAL':    (200,  20,  20),
    'HIGH':        (220, 100,   0),
    'WARNING':     (220, 180,   0),
    'AVERAGE':     (200, 140,   0),
    'UNKNOWN':     (180,  60, 180),
    'PENDING':     (100, 100, 200),
}
_DEFAULT_COLOR: Tuple[int, int, int] = (140, 140, 140)

# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------
_WIN_W: int = 1280
_WIN_H: int = 720
_FPS:   int = 60

# ---------------------------------------------------------------------------
# 3-D camera & projection
# ---------------------------------------------------------------------------
_FOV_H:   float = math.radians(75)   # horizontal field-of-view
_NEAR:    float = 0.3                 # near-clip distance (world units)
_FAR:     float = 60.0               # fog end / far clip (world units)
_FOCAL:   float = _WIN_W / (2.0 * math.tan(_FOV_H / 2.0))
_CX:      int   = _WIN_W // 2        # screen horizontal centre
_CY:      int   = _WIN_H // 2        # screen vertical centre
_EYE_H:   float = 1.7                # camera eye height above ground plane
_ARENA_R: float = 20.0               # soft arena wall radius

# ---------------------------------------------------------------------------
# Player input
# ---------------------------------------------------------------------------
_MOVE_SPEED:  float = 5.5            # world units / second
_MOUSE_SENS:  float = 0.0025         # radians / pixel
_PITCH_LIMIT: float = math.radians(65)

# ---------------------------------------------------------------------------
# Billboard (enemy target) dimensions
# ---------------------------------------------------------------------------
_BILL_W:  float = 1.4                # billboard width in world units
_BILL_H:  float = 2.0                # billboard height in world units
_BILL_CY: float = _BILL_H / 2.0     # billboard vertical centre above ground

# ---------------------------------------------------------------------------
# Scene palette
# ---------------------------------------------------------------------------
_SKY_TOP:   Tuple = ( 6,   8,  28)
_SKY_BOT:   Tuple = (18,  24,  62)
_FLOOR_TOP: Tuple = (28,  24,  18)
_FLOOR_BOT: Tuple = (10,   8,   5)
_GRID_COL:  Tuple = (38,  46,  78)


def _color_for_status(status: str) -> Tuple[int, int, int]:
    return _STATUS_COLORS.get(status.upper(), _DEFAULT_COLOR)


class _FontWrapper:
    """Thin abstraction over pygame.font / pygame.freetype.

    Some Linux distributions (e.g. Fedora, RHEL) package ``pygame.font`` as a
    separate sub-package that requires FreeType.  When it is absent the game
    loop would crash with ``NotImplementedError: font module not available``.

    This class tries ``pygame.font`` first, then ``pygame.freetype``, and
    finally falls back to a no-op stub so the game still runs (without text)
    rather than crashing.
    """

    def __init__(self, size: int) -> None:
        self._font = None   # pygame.font.Font instance
        self._ft = None     # pygame.freetype.Font instance
        self._size = size

        # Attempt 1: legacy pygame.font
        try:
            pygame.font.init()
            self._font = pygame.font.SysFont(None, size)
            return
        except Exception:
            pass

        # Attempt 2: modern pygame.freetype
        try:
            import pygame.freetype as _pft  # noqa: PLC0415
            _pft.init()
            self._ft = _pft.SysFont(None, size)
        except Exception:
            pass  # no font at all — render() will return a 1×1 blank surface

    def render(self, text: str, antialias: bool, color) -> 'pygame.Surface':
        """Return a Surface containing *text* drawn in *color*."""
        if self._font is not None:
            return self._font.render(text, antialias, color)
        if self._ft is not None:
            surf, _ = self._ft.render(text, color, size=self._size)
            return surf
        return pygame.Surface((1, 1), pygame.SRCALPHA)


def _blit_text(
    dest:  'pygame.Surface',
    src:   'pygame.Surface',
    pos:   Tuple[int, int],
    alpha: int = 255,
) -> None:
    """Blit a text surface onto *dest* applying *alpha* correctly.

    ``pygame.font`` returns whole-surface-alpha surfaces; ``pygame.freetype``
    returns per-pixel-alpha (SRCALPHA) surfaces.  Calling ``set_alpha()`` on a
    SRCALPHA surface is a no-op in pygame, so we must modulate per-pixel alpha
    separately.  This helper handles both cases.
    """
    if src.get_width() <= 1:
        return  # stub surface from _FontWrapper fallback — nothing to draw
    if alpha >= 254:
        dest.blit(src, pos)
        return
    tmp = src.copy()
    if tmp.get_flags() & pygame.SRCALPHA:
        # Per-pixel alpha: multiply each pixel's alpha channel by alpha/255
        mod = pygame.Surface(tmp.get_size(), pygame.SRCALPHA)
        mod.fill((255, 255, 255, alpha))
        tmp.blit(mod, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    else:
        tmp.set_alpha(alpha)
    dest.blit(tmp, pos)


@dataclass
class _Enemy:
    """One monitoring problem rendered as a 3-D billboard."""
    server:       object
    host_name:    str
    service_name: str       # empty string → host-level problem
    status:       str
    display_name: str
    color:        Tuple[int, int, int]
    # 3-D world position (assigned by _load_enemies)
    wx: float = 0.0
    wy: float = 0.0         # always 0 (ground plane)
    wz: float = 0.0
    # animation
    alpha: int  = 255       # 255 = fully visible; decrements on death
    dying: bool = False
    # per-frame rendering cache (excluded from equality / repr)
    _cam_dist: float = field(default=0.0, compare=False, repr=False)


class NagstamonFPSWindow(QObject):
    """Manages the pygame 3-D FPS window running in a daemon thread.

    Provides the same public interface as the former QMainWindow-based
    implementation so that callers (Nagstamon/qui/__init__.py) need no changes:

        * ``show()``           – start the game
        * ``isVisible()``      – True while the game thread is alive
        * ``raise_()``         – no-op (pygame manages its own window)
        * ``activateWindow()`` – no-op
        * ``closed`` signal    – emitted when the game window is closed
    """

    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: Optional[Thread] = None

    # ------------------------------------------------------------------
    # QWidget-compatible interface
    # ------------------------------------------------------------------

    def isVisible(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def raise_(self):
        pass

    def activateWindow(self):
        pass

    def show(self):
        """Start the pygame game loop in a daemon thread."""
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    # Game thread
    # ------------------------------------------------------------------

    def _run(self):
        try:
            self._game_loop()
        finally:
            self.closed.emit()

    def _game_loop(self):  # noqa: C901 – intentionally self-contained 3-D engine
        pygame.init()
        try:
            screen = pygame.display.set_mode((_WIN_W, _WIN_H))
            pygame.display.set_caption(
                'Nagstamon FPS Mode – Acknowledge or Die!'
            )
            clock = pygame.time.Clock()

            font_large  = _FontWrapper(28)
            font_medium = _FontWrapper(20)
            font_hud    = _FontWrapper(22)
            font_small  = _FontWrapper(16)

            # Pre-bake sky and floor gradient surfaces (height = _WIN_H each)
            sky_surf   = _make_gradient(_WIN_W, _WIN_H, _SKY_TOP,   _SKY_BOT)
            floor_surf = _make_gradient(_WIN_W, _WIN_H, _FLOOR_TOP, _FLOOR_BOT)

            enemies = self._load_enemies()
            killed  = 0

            # ── Camera state ──────────────────────────────────────────
            cam_x:     float = 0.0
            cam_y:     float = _EYE_H
            cam_z:     float = 0.0
            cam_yaw:   float = 0.0    # horizontal look (radians)
            cam_pitch: float = 0.0    # vertical look (radians, clamped)

            # ── Input / UI state ─────────────────────────────────────
            keys_held     = set()
            mouse_grabbed = False
            muzzle_flash  = 0         # ms remaining for muzzle-flash overlay
            message       = ''
            msg_timer     = 0         # ms

            def _grab(state: bool):
                nonlocal mouse_grabbed
                pygame.event.set_grab(state)
                pygame.mouse.set_visible(not state)
                mouse_grabbed = state

            _grab(True)

            running = True
            while running:
                dt_ms = clock.tick(_FPS)
                dt    = dt_ms / 1000.0

                cos_y = math.cos(cam_yaw)
                sin_y = math.sin(cam_yaw)

                # ── Events ───────────────────────────────────────────
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False

                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            if mouse_grabbed:
                                _grab(False)
                            else:
                                running = False
                        else:
                            keys_held.add(event.key)

                    elif event.type == pygame.KEYUP:
                        keys_held.discard(event.key)

                    elif event.type == pygame.MOUSEMOTION and mouse_grabbed:
                        dx_px, dy_px = event.rel
                        cam_yaw   += dx_px * _MOUSE_SENS
                        cam_pitch -= dy_px * _MOUSE_SENS
                        cam_pitch  = max(
                            -_PITCH_LIMIT, min(_PITCH_LIMIT, cam_pitch)
                        )

                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:
                            if not mouse_grabbed:
                                _grab(True)
                            else:
                                # Fire – find closest enemy overlapping crosshair
                                hit = _find_crosshair_hit(
                                    enemies, cam_x, cam_y, cam_z,
                                    cam_yaw, cam_pitch,
                                )
                                if hit is not None:
                                    hit.dying  = True
                                    killed    += 1
                                    muzzle_flash = 90
                                    message = (
                                        f'** {hit.display_name}'
                                        f' \u2013 acknowledged! **'
                                    )
                                    msg_timer = 3000
                                    self._do_acknowledge(hit)
                                else:
                                    muzzle_flash = 50   # miss flash

                # ── Movement ─────────────────────────────────────────
                fwd = stf = 0.0
                if pygame.K_w in keys_held or pygame.K_UP    in keys_held:
                    fwd += _MOVE_SPEED * dt
                if pygame.K_s in keys_held or pygame.K_DOWN  in keys_held:
                    fwd -= _MOVE_SPEED * dt
                if pygame.K_a in keys_held or pygame.K_LEFT  in keys_held:
                    stf -= _MOVE_SPEED * dt
                if pygame.K_d in keys_held or pygame.K_RIGHT in keys_held:
                    stf += _MOVE_SPEED * dt

                # Recompute after possible mouse yaw change
                cos_y = math.cos(cam_yaw)
                sin_y = math.sin(cam_yaw)

                new_x = cam_x + sin_y * fwd + cos_y * stf
                new_z = cam_z + cos_y * fwd - sin_y * stf
                # Soft arena wall – keep player inside the ring
                if new_x * new_x + new_z * new_z < _ARENA_R * _ARENA_R:
                    cam_x, cam_z = new_x, new_z

                # ── Animations ───────────────────────────────────────
                for e in enemies:
                    if e.dying:
                        e.alpha = max(0, e.alpha - int(255 * dt * 3.5))
                enemies = [e for e in enemies if e.alpha > 0]

                if muzzle_flash > 0:
                    muzzle_flash -= dt_ms
                if msg_timer > 0:
                    msg_timer -= dt_ms
                    if msg_timer <= 0:
                        message = ''

                # ── Per-enemy depth (camera-space Z) ─────────────────
                for e in enemies:
                    dx = e.wx - cam_x
                    dz = e.wz - cam_z
                    e._cam_dist = dx * sin_y + dz * cos_y

                # Sort back-to-front (painter's algorithm)
                visible = sorted(
                    [e for e in enemies if e._cam_dist > _NEAR],
                    key=lambda e: -e._cam_dist,
                )

                pitch_offset = _FOCAL * math.tan(cam_pitch)

                # ── Draw ─────────────────────────────────────────────
                _draw_sky_floor(screen, sky_surf, floor_surf, pitch_offset)
                _draw_floor_grid(screen, pitch_offset)

                for e in visible:
                    dx     = e.wx - cam_x
                    dz     = e.wz - cam_z
                    cam_rx = dx * cos_y - dz * sin_y
                    rz     = e._cam_dist            # camera-space depth
                    ry     = (e.wy + _BILL_CY) - cam_y

                    sx = int(_CX + _FOCAL * cam_rx / rz)
                    sy = int(_CY - _FOCAL * ry / rz + pitch_offset)
                    hw = max(1, int(_FOCAL * _BILL_W / (2.0 * rz)))
                    hh = max(1, int(_FOCAL * _BILL_H / (2.0 * rz)))

                    fog = max(0.0, 1.0 - rz / _FAR)
                    _draw_billboard(
                        screen, e, sx, sy, hw, hh, fog,
                        font_large, font_medium, font_small,
                    )

                # ── HUD overlay ───────────────────────────────────────
                _draw_hud(
                    screen, font_hud, font_small,
                    enemies, killed, message, msg_timer, mouse_grabbed,
                )

                # ── Muzzle flash ─────────────────────────────────────
                if muzzle_flash > 0:
                    flash = pygame.Surface((_WIN_W, _WIN_H), pygame.SRCALPHA)
                    a_flash = int(130 * max(0, muzzle_flash) / 90)
                    flash.fill((255, 220, 100, min(255, a_flash)))
                    screen.blit(flash, (0, 0))

                # ── Crosshair at screen centre ────────────────────────
                _draw_crosshair(screen, _CX, _CY)

                pygame.display.flip()
        finally:
            pygame.event.set_grab(False)
            pygame.mouse.set_visible(True)
            pygame.quit()

    @staticmethod
    def _load_enemies() -> 'List[_Enemy]':
        """Collect monitoring problems and place them in 3-D space."""
        from Nagstamon.servers import get_enabled_servers  # avoids circular import

        raw: List[_Enemy] = []

        for server in get_enabled_servers():
            for host_name, host in list(server.hosts.items()):
                if host.status not in ('UP', 'OK', ''):
                    label = f'{server.name} \xb7 {host_name} [{host.status}]'
                    raw.append(_Enemy(
                        server=server,
                        host_name=host_name,
                        service_name='',
                        status=host.status,
                        display_name=label,
                        color=_color_for_status(host.status),
                    ))
                for svc_name, svc in list(host.services.items()):
                    if svc.status not in ('UP', 'OK', ''):
                        label = (
                            f'{server.name} \xb7 {host_name}/{svc_name}'
                            f' [{svc.status}]'
                        )
                        raw.append(_Enemy(
                            server=server,
                            host_name=host_name,
                            service_name=svc_name,
                            status=svc.status,
                            display_name=label,
                            color=_color_for_status(svc.status),
                        ))

        # Place enemies in concentric rings around the origin so the player
        # starts surrounded from all sides.
        ring_radius   = 5.0
        ring_gap      = 3.5
        base_per_ring = 8       # enemies on the first ring
        rng = random.Random(42) # fixed seed for reproducible layout
        placed = ring = 0
        while placed < len(raw):
            count  = base_per_ring + ring * 4
            radius = ring_radius + ring * ring_gap
            start  = rng.uniform(0.0, 2.0 * math.pi)
            for k in range(count):
                if placed >= len(raw):
                    break
                ang = start + 2.0 * math.pi * k / count
                raw[placed].wx = radius * math.sin(ang)
                raw[placed].wz = radius * math.cos(ang)
                raw[placed].wy = 0.0
                placed += 1
            ring += 1

        return raw

    @staticmethod
    def _do_acknowledge(enemy: '_Enemy'):
        """Send an acknowledgement to the monitoring server in a daemon thread."""
        from Nagstamon.config import conf

        server = enemy.server
        try:
            username = conf.servers[server.name].username or 'nagstamon-fps'
        except (AttributeError, KeyError):
            username = 'nagstamon-fps'

        info_dict = {
            'host':                     enemy.host_name,
            'service':                  enemy.service_name,
            'author':                   username,
            'comment':                  'Acknowledged via Nagstamon FPS Mode',
            'sticky':                   True,
            'notify':                   True,
            'persistent':               True,
            'acknowledge_all_services': False,
            'all_services':             [],
        }

        def _do():
            try:
                server.set_acknowledge(info_dict)
            except Exception as exc:  # noqa: BLE001
                print(f'[Nagstamon FPS] acknowledge error: {exc}')

        Thread(target=_do, daemon=True).start()


# ---------------------------------------------------------------------------
# Module-level rendering helpers
# ---------------------------------------------------------------------------

def _make_gradient(
    w: int, h: int,
    top_col: Tuple, bot_col: Tuple,
) -> 'pygame.Surface':
    """Return a *w* × *h* Surface filled with a vertical colour gradient."""
    surf = pygame.Surface((w, h))
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top_col[0] + t * (bot_col[0] - top_col[0]))
        g = int(top_col[1] + t * (bot_col[1] - top_col[1]))
        b = int(top_col[2] + t * (bot_col[2] - top_col[2]))
        pygame.draw.line(surf, (r, g, b), (0, y), (w, y))
    return surf


def _draw_sky_floor(
    screen: 'pygame.Surface',
    sky_surf: 'pygame.Surface',
    floor_surf: 'pygame.Surface',
    pitch_offset: float,
) -> None:
    """Blit sky and floor gradient halves split at the pitch-adjusted horizon."""
    horizon_y = int(_CY + pitch_offset)

    # Sky (top portion of screen, up to the horizon)
    sky_h = max(0, min(_WIN_H, horizon_y))
    if sky_h > 0:
        screen.blit(sky_surf, (0, 0), (0, 0, _WIN_W, sky_h))

    # Floor (from horizon to screen bottom)
    floor_y = max(0, horizon_y)
    floor_h = _WIN_H - floor_y
    if floor_h > 0:
        screen.blit(floor_surf, (0, floor_y), (0, 0, _WIN_W, floor_h))


def _draw_floor_grid(
    screen: 'pygame.Surface',
    pitch_offset: float,
) -> None:
    """Draw a perspective floor grid: depth stripes + converging lines."""
    horizon_y = int(_CY + pitch_offset)
    horizon_clamped = max(0, min(_WIN_H - 1, horizon_y))

    # ── Converging lines from the vanishing point to the screen bottom ──
    # These radiate out evenly in screen-X giving a perspective-corridor feel.
    n_conv = 14
    for i in range(n_conv + 1):
        sx_bot = int(i * _WIN_W / n_conv)
        bot_y  = _WIN_H - 1
        if horizon_clamped < bot_y:
            pygame.draw.line(
                screen, _GRID_COL,
                (_CX, horizon_clamped),
                (sx_bot, bot_y),
            )

    # ── Horizontal depth stripes ─────────────────────────────────────────
    # Each stripe is the floor at a fixed distance directly ahead of the
    # camera; they converge toward the horizon with increasing distance.
    for dist in (4.0, 6.0, 9.0, 13.0, 18.0, 25.0, 36.0, 52.0):
        sy = int(_CY + _FOCAL * _EYE_H / dist + pitch_offset)
        if horizon_clamped < sy < _WIN_H:
            pygame.draw.line(screen, _GRID_COL, (0, sy), (_WIN_W - 1, sy))


def _draw_name_tag(
    screen: 'pygame.Surface',
    enemy:  '_Enemy',
    sx:     int,
    top_y:  int,
    a:      int,
    font:   '_FontWrapper',
) -> None:
    """Draw a floating pill-shaped name tag just above the billboard.

    *sx* is the billboard screen-x centre; *top_y* is the billboard's
    topmost screen-y coordinate.  The tag is always rendered (no size
    threshold) so every problem is labelled even when far away.
    """
    if a < 15:
        return

    name = enemy.display_name
    if len(name) > 44:
        name = name[:43] + '\u2026'

    r, g, b = enemy.color
    tag_surf = font.render(name, True, (255, 255, 210))
    tw, th = tag_surf.get_size()
    if tw <= 1:
        return

    pad_x, pad_y = 6, 3
    bw = tw + pad_x * 2
    bh = th + pad_y * 2

    bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
    bg_a = min(215, int(a * 0.88))
    # Dark translucent pill
    pygame.draw.rect(bg, (6, 6, 22, bg_a), (0, 0, bw, bh), border_radius=5)
    # Coloured border using status colour
    pygame.draw.rect(bg, (r, g, b, min(a, 200)), (0, 0, bw, bh), 1, border_radius=5)
    # Inner highlight line along top for a glassy look
    if bh > 6:
        pygame.draw.line(bg, (255, 255, 255, min(60, a // 3)),
                         (5, 1), (bw - 6, 1))
    _blit_text(bg, tag_surf, (pad_x, pad_y), a)

    tag_x = sx - bw // 2
    tag_y = top_y - bh - 6
    screen.blit(bg, (tag_x, tag_y))

    # Thin connector from the bottom of the tag down to the billboard top
    line_top = tag_y + bh
    if top_y > line_top + 2:
        pygame.draw.line(
            screen, (r, g, b, max(20, a // 3)),
            (sx, line_top), (sx, top_y - 1),
        )


def _draw_billboard(
    screen:      'pygame.Surface',
    enemy:       '_Enemy',
    sx:          int, sy: int,
    hw:          int, hh: int,
    fog:         float,
    font_status: '_FontWrapper',
    font_name:   '_FontWrapper',
    font_tag:    '_FontWrapper',
) -> None:
    """Render a plastic 3-D enemy billboard with a floating name tag.

    The billboard face is drawn with:

    * A dark body whose tint is derived from the status colour
    * A solid status-colour band across the top
    * A specular shine strip (horizontal gradient) just below the band
    * A left-edge rim highlight (vertical gradient) simulating a convex edge
    * A right-edge shadow for the complementary concave illusion
    * A small specular-sheen ellipse in the upper-right area
    * A bright, slightly-raised outline

    Text (status + problem name) is drawn at any billboard size, with
    ``_blit_text`` ensuring correct alpha regardless of the surface type
    returned by the font backend.  A floating name-tag pill above every
    billboard provides a label that is always readable.
    """
    if fog < 0.02:
        return
    # Horizontal cull
    if sx + hw < 0 or sx - hw > _WIN_W:
        return
    # Vertical cull
    if sy + hh < 0 or sy - hh > _WIN_H:
        return

    a = int(enemy.alpha * fog)
    if a <= 0:
        return

    r, g, b = enemy.color
    w, h    = hw * 2, hh * 2
    rad     = max(3, min(14, w // 8))

    surf = pygame.Surface((w, h), pygame.SRCALPHA)

    # ── 1. Dark tinted plastic body ──────────────────────────────────────
    # Derive a mid-range body colour from the status hue so the panel still
    # reads as the right severity even without the bright band.
    bdy_r = min(255, r // 4 + 18)
    bdy_g = min(255, g // 4 + 12)
    bdy_b = min(255, b // 4 + 48)
    pygame.draw.rect(
        surf,
        (bdy_r, bdy_g, bdy_b, min(235, int(a * 0.92))),
        (0, 0, w, h),
        border_radius=rad,
    )

    # ── 2. Status-colour top band ─────────────────────────────────────────
    band_h = max(5, h * 2 // 9)
    pygame.draw.rect(
        surf, (r, g, b, min(a, 218)),
        (0, 0, w, band_h), border_radius=rad,
    )
    # Flatten the bottom corners of the band so it reads as a straight bar
    if band_h < h - 1 and band_h > rad:
        pygame.draw.rect(
            surf, (r, g, b, min(a, 218)),
            (0, rad, w, max(1, band_h - rad)),
        )
    # Inner top-edge shine on the band (glassy)
    if band_h > 3:
        pygame.draw.line(
            surf,
            (min(255, r + 90), min(255, g + 90), min(255, b + 90), min(a, 130)),
            (rad + 1, 1), (w - rad - 2, 1),
        )

    # ── 3. Plastic specular shine below the band ──────────────────────────
    n_shine = min(8, max(2, h // 12))
    for i in range(n_shine):
        t  = 1.0 - i / n_shine
        sa = int(a * 0.42 * t)
        if sa > 1 and band_h + i < h - 1:
            pygame.draw.line(
                surf, (255, 255, 255, sa),
                (rad + 1, band_h + i), (w - rad - 2, band_h + i),
            )

    # ── 4. Left rim highlight (convex moulding edge) ──────────────────────
    n_rim = min(4, max(1, w // 20))
    for i in range(n_rim):
        t  = 1.0 - i / n_rim
        ra = int(a * 0.36 * t)
        if ra > 1 and 1 + i < w - 1:
            pygame.draw.line(
                surf, (255, 255, 255, ra),
                (1 + i, rad + 2), (1 + i, h - rad - 3),
            )

    # ── 5. Right-edge shadow (recessed right side) ────────────────────────
    n_shad = min(4, max(1, w // 20))
    for i in range(n_shad):
        t   = 1.0 - i / n_shad
        sha = int(a * 0.32 * t)
        if sha > 1 and w - 2 - i > 0:
            pygame.draw.line(
                surf, (0, 0, 0, sha),
                (w - 2 - i, rad + 2), (w - 2 - i, h - rad - 3),
            )

    # ── 6. Bright raised outline ──────────────────────────────────────────
    bord_r = min(255, r + 72)
    bord_g = min(255, g + 72)
    bord_b = min(255, b + 72)
    border_w = max(1, w // 50 + 1)
    pygame.draw.rect(
        surf, (bord_r, bord_g, bord_b, a),
        (0, 0, w, h), border_w, border_radius=rad,
    )

    # ── 7. Specular highlight ellipse (upper-right sheen dot) ─────────────
    if w >= 20 and h >= 14:
        ex = w * 3 // 4
        ey = band_h + max(2, (h - band_h) // 8)
        er = max(2, min(w // 7, (h - band_h) // 6))
        pygame.draw.ellipse(
            surf, (255, 255, 255, min(a // 2, 88)),
            (ex - er, ey - er // 2, er * 2, max(1, er)),
        )

    # ── 8. Status text (always rendered, no size gate) ────────────────────
    text_y = band_h + 2
    if h > 16:
        st = font_status.render(enemy.status, True, (255, 255, 255))
        _blit_text(surf, st, (4, text_y), a)
        text_y += max(st.get_height(), 1) + 1

    # ── 9. Problem name on billboard face ─────────────────────────────────
    if h > 10:
        max_chars = max(3, (w - 8) // 7)
        name = enemy.display_name
        if len(name) > max_chars:
            name = name[:max_chars - 1] + '\u2026'
        nm = font_name.render(name, True, (215, 232, 255))
        _blit_text(surf, nm, (4, text_y), a)

    screen.blit(surf, (sx - hw, sy - hh))

    # ── 10. Floating name-tag above the billboard ─────────────────────────
    _draw_name_tag(screen, enemy, sx, sy - hh, a, font_tag)


def _find_crosshair_hit(
    enemies: 'List[_Enemy]',
    cam_x: float, cam_y: float, cam_z: float,
    cam_yaw: float, cam_pitch: float,
) -> 'Optional[_Enemy]':
    """Return the closest alive enemy whose billboard overlaps the crosshair."""
    cos_y = math.cos(cam_yaw)
    sin_y = math.sin(cam_yaw)
    pitch_offset = _FOCAL * math.tan(cam_pitch)

    best_dist: float = _FAR
    best_e: Optional[_Enemy] = None

    for e in enemies:
        if e.dying:
            continue
        dx = e.wx - cam_x
        dz = e.wz - cam_z
        cam_rx = dx * cos_y - dz * sin_y
        rz     = dx * sin_y + dz * cos_y
        if rz <= _NEAR:
            continue
        ry = (e.wy + _BILL_CY) - cam_y

        sx = int(_CX + _FOCAL * cam_rx / rz)
        sy = int(_CY - _FOCAL * ry / rz + pitch_offset)
        hw = max(1, int(_FOCAL * _BILL_W / (2.0 * rz)))
        hh = max(1, int(_FOCAL * _BILL_H / (2.0 * rz)))

        if (sx - hw <= _CX <= sx + hw
                and sy - hh <= _CY <= sy + hh
                and rz < best_dist):
            best_dist = rz
            best_e    = e

    return best_e


def _draw_hud(
    screen: 'pygame.Surface',
    font_hud:   '_FontWrapper',
    font_small: '_FontWrapper',
    enemies:    'List[_Enemy]',
    killed:     int,
    message:    str,
    msg_timer:  int,
    mouse_grabbed: bool,
) -> None:
    """Draw the HUD: top stat bar, bottom hint bar, and optional messages."""
    remaining = sum(1 for e in enemies if not e.dying)

    # Top bar
    bar = pygame.Surface((_WIN_W, 40), pygame.SRCALPHA)
    bar.fill((0, 0, 0, 150))
    screen.blit(bar, (0, 0))
    pygame.draw.line(screen, (50, 65, 120), (0, 39), (_WIN_W, 39))

    hud_text = (
        f'Targets: {remaining} remaining  \xb7  {killed} acknowledged'
    )
    h_surf = font_hud.render(hud_text, True, (190, 205, 255))
    screen.blit(h_surf, (14, (40 - h_surf.get_height()) // 2))

    # Bottom hint bar
    bot = pygame.Surface((_WIN_W, 26), pygame.SRCALPHA)
    bot.fill((0, 0, 0, 130))
    screen.blit(bot, (0, _WIN_H - 26))
    pygame.draw.line(screen, (50, 65, 120), (0, _WIN_H - 26), (_WIN_W, _WIN_H - 26))

    action = 'exit' if mouse_grabbed else 'resume (click to re-grab mouse)'
    hint = (
        'WASD / \u2191\u2193\u2190\u2192 : move   '
        'Mouse : look   '
        'LMB : fire / acknowledge   '
        f'ESC : {action}'
    )
    hint_surf = font_small.render(hint, True, (115, 120, 160))
    screen.blit(
        hint_surf,
        (14, _WIN_H - 26 + (26 - hint_surf.get_height()) // 2),
    )

    # Kill / acknowledge message (fades out)
    if message:
        fade = min(1.0, msg_timer / 400.0)
        msg_surf = font_hud.render(message, True, (255, 210, 60))
        msg_surf.set_alpha(int(255 * fade))
        screen.blit(
            msg_surf,
            (_CX - msg_surf.get_width() // 2, _WIN_H // 3),
        )

    # All-clear message
    if not any(not e.dying for e in enemies):
        clr = font_hud.render(
            'All systems go!  No problems to fight.',
            True, (80, 220, 80),
        )
        screen.blit(clr, (_CX - clr.get_width() // 2, _CY - clr.get_height() // 2))

    # Mouse-ungrabbed dim overlay
    if not mouse_grabbed:
        ov = pygame.Surface((_WIN_W, _WIN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 110))
        screen.blit(ov, (0, 0))
        click = font_hud.render('Click to resume', True, (255, 255, 255))
        screen.blit(click, (_CX - click.get_width() // 2, _CY - click.get_height() // 2))


def _draw_crosshair(surface: 'pygame.Surface', x: int, y: int) -> None:
    """Draw a first-person crosshair fixed at screen centre *(x, y)*."""
    col_fg = (255, 255,  80)
    col_bg = (  0,   0,   0)
    gap, arm, thick = 6, 13, 2

    # Shadow (black, slightly offset)
    for x0, y0, x1, y1 in [
        (x - arm - gap - 1, y, x - gap - 1, y),
        (x + gap + 1,       y, x + arm + gap + 1, y),
        (x, y - arm - gap - 1, x, y - gap - 1),
        (x, y + gap + 1,       x, y + arm + gap + 1),
    ]:
        pygame.draw.line(surface, col_bg, (x0, y0), (x1, y1), thick + 2)

    # Foreground arms
    pygame.draw.line(surface, col_fg, (x - arm - gap, y), (x - gap, y), thick)
    pygame.draw.line(surface, col_fg, (x + gap,       y), (x + arm + gap, y), thick)
    pygame.draw.line(surface, col_fg, (x, y - arm - gap), (x, y - gap), thick)
    pygame.draw.line(surface, col_fg, (x, y + gap),       (x, y + arm + gap), thick)

    # Centre dot (shadow then fill)
    pygame.draw.circle(surface, col_bg, (x, y), 4)
    pygame.draw.circle(surface, col_fg, (x, y), 3)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def show_fps_window(parent=None) -> Optional[NagstamonFPSWindow]:
    """Create and show the FPS window, or display an install hint if pygame is missing.

    Returns the :class:`NagstamonFPSWindow` instance, or ``None`` when pygame
    is not available.
    """
    if not PYGAME_AVAILABLE:
        from PyQt6.QtWidgets import QMessageBox
        if _PYGAME_IMPORT_ERROR:
            detail = (
                f'Error:\n    {_PYGAME_IMPORT_ERROR}\n\n'
                'Install with:\n    pip install pygame'
            )
        else:
            detail = 'Please install the pygame package:\n    pip install pygame'
        QMessageBox.warning(
            parent,
            'Nagstamon FPS Mode',
            f'pygame is not available.\n\n{detail}',
        )
        return None

    window = NagstamonFPSWindow(parent)
    window.show()
    return window
