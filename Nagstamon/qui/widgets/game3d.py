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
                        font_large, font_medium,
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


def _draw_billboard(
    screen: 'pygame.Surface',
    enemy: '_Enemy',
    sx: int, sy: int,
    hw: int, hh: int,
    fog: float,
    font_large:  '_FontWrapper',
    font_medium: '_FontWrapper',
) -> None:
    """Render one 3-D enemy billboard onto *screen*."""
    if fog < 0.02:
        return
    # Cull fully off-screen billboards
    if sx + hw < 0 or sx - hw > _WIN_W:
        return
    if sy + hh < 0 or sy - hh > _WIN_H:
        return

    a   = int(enemy.alpha * fog)
    r, g, b = enemy.color
    w, h    = hw * 2, hh * 2

    surf = pygame.Surface((w, h), pygame.SRCALPHA)

    # Dark background panel
    bg_a = min(200, int(a * 0.65))
    pygame.draw.rect(
        surf, (r // 6, g // 6, b // 6, bg_a),
        (0, 0, w, h), border_radius=6,
    )
    # Coloured border
    pygame.draw.rect(
        surf, (r, g, b, a),
        (0, 0, w, h), 2, border_radius=6,
    )
    # Severity glow strip at top
    glow_h = max(4, h // 6)
    pygame.draw.rect(
        surf, (r, g, b, min(a, 170)),
        (2, 2, w - 4, glow_h), border_radius=4,
    )

    # Status text (only when billboard is large enough to be readable)
    text_y = glow_h + 4
    if hw > 28:
        st = font_large.render(enemy.status, True, (255, 255, 255))
        st.set_alpha(a)
        surf.blit(st, (6, text_y))
        text_y += st.get_height() + 2

    if hw > 48:
        max_chars = max(4, w // 7)
        name = enemy.display_name
        if len(name) > max_chars:
            name = name[:max_chars - 2] + '\u2026'
        nm = font_medium.render(name, True, (200, 200, 200))
        nm.set_alpha(a)
        surf.blit(nm, (6, text_y))

    screen.blit(surf, (sx - hw, sy - hh))


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
