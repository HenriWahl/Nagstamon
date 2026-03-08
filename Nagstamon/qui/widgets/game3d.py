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

"""Nagstamon FPS Mode – inspired by psdoom.

Monitoring problems retrieved from all enabled servers are rendered as
coloured targets in a shooting-gallery scene powered by pygame.
Click on a target to acknowledge the corresponding monitoring problem.

Controls
--------
* **Click** on a target        – acknowledge (kill) the problem
* **Mouse wheel / Arrow keys** – scroll through targets when there are many
* **Escape** or close window   – exit FPS mode

Requires the ``pygame`` package::

    pip install pygame
"""

import math
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
# Layout constants
# ---------------------------------------------------------------------------
_WIN_W:      int = 1280
_WIN_H:      int = 720
_FPS:        int = 60
_BG_COLOR        = (10, 14, 40)
_HEADER_H:   int = 44
_FOOTER_H:   int = 28
_COLS:       int = 4
_TARGET_W:   int = 300
_TARGET_H:   int = 84
_TARGET_PAD: int = 12
_SCROLL_SPEED: int = 30


def _color_for_status(status: str) -> Tuple[int, int, int]:
    return _STATUS_COLORS.get(status.upper(), _DEFAULT_COLOR)


@dataclass
class _Enemy:
    """One monitoring problem rendered as a clickable target."""
    server: object       # GenericServer instance
    host_name: str
    service_name: str    # empty string → host-level problem
    status: str
    display_name: str
    color: Tuple[int, int, int]
    rect: object = field(default=None)  # pygame.Rect; assigned during layout
    alpha: int = 255                    # 255 = fully visible; decrements on death
    dying: bool = False


class NagstamonFPSWindow(QObject):
    """Manages the pygame FPS window running in a daemon thread.

    Provides the same public interface as the former QMainWindow-based
    implementation so that callers (Nagstamon/qui/__init__.py) need no changes:

        * ``show()``          – start the game
        * ``isVisible()``     – True while the game thread is alive
        * ``raise_()``        – no-op (pygame manages its own window)
        * ``activateWindow()``– no-op
        * ``closed`` signal   – emitted when the game window is closed
    """

    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: Optional[Thread] = None

    # ------------------------------------------------------------------
    # QWidget-compatible interface (used by Nagstamon/qui/__init__.py)
    # ------------------------------------------------------------------

    def isVisible(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def raise_(self):
        pass  # pygame window focus is managed by the OS

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

    def _game_loop(self):  # noqa: C901 – intentionally self-contained
        pygame.init()
        try:
            screen = pygame.display.set_mode((_WIN_W, _WIN_H))
            pygame.display.set_caption(
                'Nagstamon FPS Mode – Click to Acknowledge!'
            )
            pygame.mouse.set_visible(False)
            clock = pygame.time.Clock()

            font_status = pygame.font.SysFont(None, 30)
            font_name   = pygame.font.SysFont(None, 20)
            font_hud    = pygame.font.SysFont(None, 22)
            font_hint   = pygame.font.SysFont(None, 18)

            enemies = self._load_enemies()
            killed    = 0
            scroll_y  = 0
            message   = ''
            msg_timer = 0

            viewport_h = _WIN_H - _HEADER_H - _FOOTER_H

            def _content_height() -> int:
                rows = math.ceil(len(enemies) / _COLS) if enemies else 0
                return rows * (_TARGET_H + _TARGET_PAD) + _TARGET_PAD

            running = True
            while running:
                dt = clock.tick(_FPS)

                # ── Events ───────────────────────────────────────────
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            running = False
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            scroll_y = min(
                                max(0, _content_height() - viewport_h),
                                scroll_y + _SCROLL_SPEED,
                            )
                        elif event.key in (pygame.K_UP, pygame.K_w):
                            scroll_y = max(0, scroll_y - _SCROLL_SPEED)
                    elif event.type == pygame.MOUSEWHEEL:
                        max_scroll = max(0, _content_height() - viewport_h)
                        scroll_y = max(
                            0,
                            min(max_scroll, scroll_y - event.y * _SCROLL_SPEED),
                        )
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        mx, my = event.pos
                        if _HEADER_H <= my < _WIN_H - _FOOTER_H:
                            # Translate screen → content coordinates
                            cx = mx
                            cy = my - _HEADER_H + scroll_y
                            for enemy in enemies:
                                if (not enemy.dying
                                        and enemy.rect.collidepoint(cx, cy)):
                                    enemy.dying = True
                                    killed += 1
                                    message = (
                                        f'** {enemy.display_name}'
                                        f' - acknowledged! **'
                                    )
                                    msg_timer = 3000
                                    self._do_acknowledge(enemy)
                                    break

                # ── Animations ───────────────────────────────────────
                for enemy in enemies:
                    if enemy.dying:
                        enemy.alpha = max(0, enemy.alpha - 10)
                enemies = [e for e in enemies if e.alpha > 0]

                if msg_timer > 0:
                    msg_timer -= dt
                    if msg_timer <= 0:
                        message = ''

                # Clamp scroll after enemies are removed
                max_scroll = max(0, _content_height() - viewport_h)
                scroll_y = min(scroll_y, max_scroll)

                # ── Draw ─────────────────────────────────────────────
                screen.fill(_BG_COLOR)
                mx_cur, my_cur = pygame.mouse.get_pos()

                # Clip drawing to the content viewport
                screen.set_clip(pygame.Rect(0, _HEADER_H, _WIN_W, viewport_h))

                for enemy in enemies:
                    sx = enemy.rect.x
                    sy = enemy.rect.y - scroll_y + _HEADER_H
                    # Skip if fully outside the viewport
                    if sy + _TARGET_H <= _HEADER_H or sy >= _WIN_H - _FOOTER_H:
                        continue

                    surf = pygame.Surface(
                        (_TARGET_W, _TARGET_H), pygame.SRCALPHA
                    )
                    a = enemy.alpha
                    r, g, b = enemy.color

                    # Background fill (semi-transparent)
                    pygame.draw.rect(
                        surf, (r, g, b, max(30, a // 3)),
                        (0, 0, _TARGET_W, _TARGET_H), border_radius=8,
                    )
                    # Coloured border
                    pygame.draw.rect(
                        surf, (r, g, b, a),
                        (0, 0, _TARGET_W, _TARGET_H), 2, border_radius=8,
                    )

                    # Status label
                    st_surf = font_status.render(enemy.status, True, (255, 255, 255))
                    st_surf.set_alpha(a)
                    surf.blit(st_surf, (10, 8))

                    # Problem name (truncated)
                    name = enemy.display_name
                    if len(name) > 44:
                        name = name[:41] + '...'
                    nm_surf = font_name.render(name, True, (210, 210, 210))
                    nm_surf.set_alpha(a)
                    surf.blit(nm_surf, (10, 46))

                    # Hover highlight
                    scr_rect = pygame.Rect(sx, sy, _TARGET_W, _TARGET_H)
                    if scr_rect.collidepoint(mx_cur, my_cur) and not enemy.dying:
                        pygame.draw.rect(
                            surf, (255, 255, 255, 40),
                            (0, 0, _TARGET_W, _TARGET_H), border_radius=8,
                        )

                    screen.blit(surf, (sx, sy))

                screen.set_clip(None)

                # ── Header ───────────────────────────────────────────
                remaining = sum(1 for e in enemies if not e.dying)
                hud_text = (
                    f'Problems: {remaining} remaining  \xb7  '
                    f'{killed} acknowledged'
                )
                hud_surf = font_hud.render(hud_text, True, (200, 200, 200))
                screen.blit(
                    hud_surf,
                    (12, (_HEADER_H - hud_surf.get_height()) // 2),
                )
                pygame.draw.line(
                    screen, (50, 60, 90),
                    (0, _HEADER_H - 1), (_WIN_W, _HEADER_H - 1),
                )

                # Scroll indicator bar
                if max_scroll > 0:
                    bar_h = max(
                        20, int(viewport_h * viewport_h / _content_height())
                    )
                    bar_y = _HEADER_H + int(
                        scroll_y * (viewport_h - bar_h) / max_scroll
                    )
                    pygame.draw.rect(
                        screen, (80, 90, 130),
                        (_WIN_W - 6, bar_y, 5, bar_h), border_radius=2,
                    )

                # ── Kill / status message ─────────────────────────────
                if message:
                    fade = min(1.0, msg_timer / 500.0)
                    msg_surf = font_hud.render(
                        message, True, (255, 200, 100)
                    )
                    msg_surf.set_alpha(int(255 * fade))
                    screen.blit(
                        msg_surf,
                        (
                            _WIN_W // 2 - msg_surf.get_width() // 2,
                            _WIN_H // 3,
                        ),
                    )

                if not any(not e.dying for e in enemies):
                    clear_surf = font_status.render(
                        'All systems go!  No problems to fight.',
                        True, (100, 220, 100),
                    )
                    screen.blit(
                        clear_surf,
                        (
                            _WIN_W // 2 - clear_surf.get_width() // 2,
                            _WIN_H // 2,
                        ),
                    )

                # ── Footer ───────────────────────────────────────────
                pygame.draw.line(
                    screen, (50, 60, 90),
                    (0, _WIN_H - _FOOTER_H), (_WIN_W, _WIN_H - _FOOTER_H),
                )
                hint = (
                    'Click on a target to acknowledge it'
                    '   |   Scroll: mouse wheel / arrow keys'
                    '   |   ESC: exit'
                )
                hint_surf = font_hint.render(hint, True, (120, 120, 140))
                screen.blit(
                    hint_surf,
                    (
                        12,
                        _WIN_H - _FOOTER_H
                        + (_FOOTER_H - hint_surf.get_height()) // 2,
                    ),
                )

                # ── Crosshair cursor ─────────────────────────────────
                _draw_crosshair(screen, mx_cur, my_cur)

                pygame.display.flip()
        finally:
            pygame.quit()

    @staticmethod
    def _load_enemies() -> 'List[_Enemy]':
        """Collect all active monitoring problems and arrange them in a grid."""
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
                            f'{server.name} \xb7 {host_name} / {svc_name}'
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

        # Assign grid positions (content-area coordinates)
        for i, enemy in enumerate(raw):
            col = i % _COLS
            row = i // _COLS
            x = _TARGET_PAD + col * (_TARGET_W + _TARGET_PAD)
            y = _TARGET_PAD + row * (_TARGET_H + _TARGET_PAD)
            enemy.rect = pygame.Rect(x, y, _TARGET_W, _TARGET_H)

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


def _draw_crosshair(surface, x: int, y: int) -> None:
    """Draw a simple crosshair cursor at *(x, y)*."""
    color = (255, 255, 100)
    gap, arm, thickness = 5, 14, 2
    # Horizontal arms
    pygame.draw.line(surface, color, (x - arm - gap, y), (x - gap, y), thickness)
    pygame.draw.line(surface, color, (x + gap, y), (x + arm + gap, y), thickness)
    # Vertical arms
    pygame.draw.line(surface, color, (x, y - arm - gap), (x, y - gap), thickness)
    pygame.draw.line(surface, color, (x, y + gap), (x, y + arm + gap), thickness)
    # Centre dot
    pygame.draw.circle(surface, color, (x, y), 3)


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
