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
coloured 3-D enemies in a first-person-shooter scene powered by Qt3D.
Clicking an enemy acknowledges the corresponding monitoring problem and
removes it from the scene.

Controls
--------
* **W / A / S / D** or **Arrow keys** – move the camera
* **Left-button drag** – look around
* **Click on an enemy** – acknowledge (kill) the problem

Requires the ``PyQt6-3D`` package::

    pip install PyQt6-3D
"""

import hashlib
import random
from dataclasses import dataclass
from threading import Thread
from typing import Dict, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QVector3D
from PyQt6.QtWidgets import QLabel, QMainWindow, QWidget, QVBoxLayout

_QT3D_IMPORT_ERROR: str = ''
try:
    from PyQt6.Qt3DCore import QEntity
    from PyQt6.Qt3DCore import QTransform as Qt3DTransform
    from PyQt6.Qt3DExtras import (
        QConeMesh,
        QCuboidMesh,
        QCylinderMesh,
        QFirstPersonCameraController,
        QPhongMaterial,
        QPlaneMesh,
        QSphereMesh,
        Qt3DWindow,
    )
    from PyQt6.Qt3DRender import QObjectPicker, QPickingSettings, QPointLight
    QT3D_AVAILABLE = True
except Exception as _exc:
    # Catch *any* failure – not just ImportError.
    # On Python 3.14+ and certain linkers, an ABI mismatch (e.g.
    # "undefined symbol: ..., version Qt_6_PRIVATE_API") surfaces as
    # OSError from dlopen() rather than ImportError, so a bare
    # "except ImportError" would miss it and crash Nagstamon at startup.
    QT3D_AVAILABLE = False
    _QT3D_IMPORT_ERROR = str(_exc)

# ---------------------------------------------------------------------------
# Appearance mapping:  monitoring status  →  (mesh_type, QColor, scale)
# ---------------------------------------------------------------------------
_STATUS_APPEARANCE = {
    'DOWN':        ('sphere',   QColor(220,  30,  30), 1.4),
    'UNREACHABLE': ('sphere',   QColor(160,  20,  20), 1.2),
    'DISASTER':    ('sphere',   QColor(255,   0,   0), 1.6),
    'CRITICAL':    ('cube',     QColor(200,  20,  20), 1.2),
    'HIGH':        ('cube',     QColor(220, 100,   0), 1.1),
    'WARNING':     ('cone',     QColor(220, 180,   0), 1.2),
    'AVERAGE':     ('cone',     QColor(200, 140,   0), 1.0),
    'UNKNOWN':     ('cylinder', QColor(180,  60, 180), 1.0),
    'PENDING':     ('cylinder', QColor(100, 100, 200), 0.8),
}
_DEFAULT_APPEARANCE = ('cube', QColor(140, 140, 140), 1.0)


def _appearance(status: str):
    """Return ``(mesh_type, color, scale)`` for the given monitoring status."""
    return _STATUS_APPEARANCE.get(status.upper(), _DEFAULT_APPEARANCE)


def _deterministic_pos(seed: str, used: set, spread: float = 38.0) -> 'QVector3D':
    """Return a deterministic, collision-free XZ position for an enemy.

    The position is derived from a hash of *seed* so that the same problem
    always spawns at the same location on every game launch.
    """
    digest = hashlib.md5(seed.encode(), usedforsecurity=False).hexdigest()[:8]
    rng = random.Random(int(digest, 16))
    last_x, last_z = 0.0, -10.0
    for _ in range(300):
        last_x = rng.uniform(-spread, spread)
        last_z = rng.uniform(-6.0, -spread * 2.2)
        if all(
            abs(last_x - px) > 3.0 or abs(last_z - pz) > 3.0
            for px, pz in used
        ):
            used.add((round(last_x, 2), round(last_z, 2)))
            return QVector3D(last_x, 1.0, last_z)
    # Exhausted attempts – use the last computed position without checking
    return QVector3D(last_x, 1.0, last_z)


@dataclass
class EnemyInfo:
    """Links a Qt3D entity to a monitoring problem."""
    server: object      # GenericServer instance
    host_name: str
    service_name: str   # empty string  →  host-level problem
    status: str
    display_name: str   # human-readable label shown in the HUD on kill


class NagstamonFPSWindow(QMainWindow):
    """FPS window where monitoring problems appear as coloured 3-D enemies.

    Click on an enemy to acknowledge (kill) the corresponding monitoring
    problem on the server.  The entity is then removed from the scene.
    """

    closed = pyqtSignal()

    # --- HUD stylesheet constants ---
    _SCORE_STYLE = (
        'color:#ffffff; font-size:13px; background:rgba(0,0,0,160);'
        ' padding:4px 10px; border-radius:4px;'
    )
    _MSG_STYLE = (
        'color:#ff4444; font-size:17px; font-weight:bold;'
        ' background:transparent;'
    )
    _HELP_STYLE = (
        'color:rgba(220,220,220,180); font-size:11px;'
        ' background:rgba(0,0,0,110); padding:4px 8px;'
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Nagstamon FPS Mode – Shoot to Acknowledge!')
        self.resize(1280, 720)

        self._enemies: Dict[object, EnemyInfo] = {}
        self._killed: int = 0

        self._msg_timer = QTimer(self)
        self._msg_timer.setSingleShot(True)
        self._msg_timer.timeout.connect(self._clear_message)

        self._setup_ui()
        self._setup_scene()
        self._load_problems()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Create the Qt3D container and transparent HUD overlay labels."""
        central = QWidget(self)
        self.setCentralWidget(central)

        # Qt3D window embedded in a QWidget container
        self._view = Qt3DWindow()
        self._view.defaultFrameGraph().setClearColor(QColor(10, 14, 40))

        container = QWidget.createWindowContainer(self._view, central)
        container.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        container.setMinimumSize(640, 400)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(container)

        wattr = Qt.WidgetAttribute.WA_TransparentForMouseEvents

        # Crosshair — centre of the viewport
        self._crosshair = QLabel('⊕', central)
        self._crosshair.setStyleSheet(
            'color:rgba(255,255,128,220); font-size:26px; background:transparent;'
        )
        self._crosshair.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._crosshair.setAttribute(wattr)

        # Score / problem counter — top-left
        self._score_label = QLabel('', central)
        self._score_label.setStyleSheet(self._SCORE_STYLE)
        self._score_label.setAttribute(wattr)

        # Feedback message — centre
        self._msg_label = QLabel('', central)
        self._msg_label.setStyleSheet(self._MSG_STYLE)
        self._msg_label.setAttribute(wattr)

        # Controls hint — bottom-left
        self._help_label = QLabel(
            'WASD / Arrows: Move  ·  Left-drag: Look  ·  Click enemy: Acknowledge',
            central,
        )
        self._help_label.setStyleSheet(self._HELP_STYLE)
        self._help_label.setAttribute(wattr)

        # Position overlays once the window event loop is running
        QTimer.singleShot(0, self._reposition_overlays)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_overlays()

    def _reposition_overlays(self):
        """Place all HUD labels relative to the current window dimensions."""
        cw = self.centralWidget()
        if not cw:
            return
        w, h = cw.width(), cw.height()
        if w < 1 or h < 1:
            return

        # Crosshair centred
        self._crosshair.adjustSize()
        cxw, cxh = self._crosshair.width(), self._crosshair.height()
        self._crosshair.setGeometry(
            (w - cxw) // 2, (h - cxh) // 2, cxw, cxh
        )
        self._crosshair.raise_()

        # Score top-left
        self._score_label.adjustSize()
        self._score_label.move(12, 12)
        self._score_label.raise_()

        # Message centred, upper-third
        self._msg_label.adjustSize()
        self._msg_label.move(
            max(0, (w - self._msg_label.width()) // 2), h // 3
        )
        self._msg_label.raise_()

        # Help hint bottom-left
        self._help_label.adjustSize()
        self._help_label.move(12, h - self._help_label.height() - 12)
        self._help_label.raise_()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # 3-D scene
    # ------------------------------------------------------------------

    def _setup_scene(self):
        """Initialise the Qt3D root entity, camera, camera controller, lights, and floor."""
        self._root = QEntity()

        # Camera
        camera = self._view.camera()
        camera.lens().setPerspectiveProjection(65.0, 16.0 / 9.0, 0.1, 1000.0)
        camera.setPosition(QVector3D(0.0, 2.0, 5.0))
        camera.setUpVector(QVector3D(0.0, 1.0, 0.0))
        camera.setViewCenter(QVector3D(0.0, 1.5, -1.0))

        # First-person camera controller (WASD + left-drag)
        ctrl = QFirstPersonCameraController(self._root)
        ctrl.setLinearSpeed(14.0)
        ctrl.setLookSpeed(130.0)
        ctrl.setCamera(camera)

        # Enable object picking so QObjectPicker components fire on click
        rs = self._view.renderSettings()
        ps = rs.pickingSettings()
        ps.setPickMethod(QPickingSettings.PickMethod.BoundingVolumePicking)
        ps.setPickResultMode(QPickingSettings.PickResultMode.NearestPick)

        # Lights
        self._add_point_light(QVector3D(0.0, 30.0,  15.0), QColor(255, 245, 220), 1.0)
        self._add_point_light(QVector3D(0.0,  5.0,  20.0), QColor(100, 120, 200), 0.4)

        # Ground plane
        self._create_floor()

        self._view.setRootEntity(self._root)

    def _add_point_light(
        self,
        position: 'QVector3D',
        color: 'QColor',
        intensity: float,
    ):
        """Add a positioned point light to the root entity."""
        entity = QEntity(self._root)
        light = QPointLight(entity)
        light.setColor(color)
        light.setIntensity(intensity)
        t = Qt3DTransform(entity)
        t.setTranslation(position)
        entity.addComponent(light)
        entity.addComponent(t)

    def _create_floor(self):
        """Create a large, dark-green horizontal ground plane."""
        floor = QEntity(self._root)
        mesh = QPlaneMesh()
        mesh.setWidth(300.0)
        mesh.setHeight(300.0)
        mat = QPhongMaterial(floor)
        mat.setDiffuse(QColor(28, 65, 28))
        mat.setAmbient(QColor(12, 30, 12))
        mat.setSpecular(QColor(8, 16, 8))
        mat.setShininess(5.0)
        t = Qt3DTransform(floor)
        t.setTranslation(QVector3D(0.0, 0.0, 0.0))
        floor.addComponent(mesh)
        floor.addComponent(mat)
        floor.addComponent(t)

    # ------------------------------------------------------------------
    # Enemy loading
    # ------------------------------------------------------------------

    def _load_problems(self):
        """Iterate over all enabled servers and spawn an enemy for each active problem."""
        from Nagstamon.servers import get_enabled_servers  # local import avoids circular deps

        used_positions: set = set()

        for server in get_enabled_servers():
            for host_name, host in list(server.hosts.items()):
                # Host-level problem (down / unreachable / disaster …)
                if host.status not in ('UP', 'OK', ''):
                    pos = _deterministic_pos(
                        f'{server.name}:{host_name}', used_positions
                    )
                    label = f'{server.name} · {host_name} [{host.status}]'
                    self._spawn_enemy(
                        server, host_name, '', host.status, label, pos
                    )

                # Service-level problems
                for svc_name, svc in list(host.services.items()):
                    if svc.status not in ('UP', 'OK', ''):
                        pos = _deterministic_pos(
                            f'{server.name}:{host_name}/{svc_name}',
                            used_positions,
                        )
                        label = (
                            f'{server.name} · {host_name} / {svc_name}'
                            f' [{svc.status}]'
                        )
                        self._spawn_enemy(
                            server, host_name, svc_name, svc.status, label, pos
                        )

        self._update_score()
        if not self._enemies:
            self._show_message('All systems go! No problems to fight.')

    def _spawn_enemy(
        self,
        server,
        host_name: str,
        service_name: str,
        status: str,
        display_name: str,
        position: 'QVector3D',
    ):
        """Create a single enemy entity in the scene and register it."""
        entity = QEntity(self._root)
        mesh_type, color, scale = _appearance(status)

        # --- mesh ---
        if mesh_type == 'sphere':
            mesh = QSphereMesh()
            mesh.setRadius(0.85 * scale)
        elif mesh_type == 'cone':
            mesh = QConeMesh()
            mesh.setLength(1.8 * scale)
            mesh.setBottomRadius(0.7 * scale)
            mesh.setTopRadius(0.0)
        elif mesh_type == 'cylinder':
            mesh = QCylinderMesh()
            mesh.setRadius(0.55 * scale)
            mesh.setLength(1.8 * scale)
        else:  # cube (default)
            mesh = QCuboidMesh()
            side = 1.4 * scale
            mesh.setXExtent(side)
            mesh.setYExtent(side)
            mesh.setZExtent(side)
        entity.addComponent(mesh)

        # --- material ---
        mat = QPhongMaterial(entity)
        mat.setDiffuse(color)
        mat.setAmbient(
            QColor(
                max(0, color.red() // 4),
                max(0, color.green() // 4),
                max(0, color.blue() // 4),
            )
        )
        mat.setSpecular(QColor(200, 200, 200))
        mat.setShininess(60.0)
        entity.addComponent(mat)

        # --- transform ---
        t = Qt3DTransform(entity)
        t.setTranslation(position)
        entity.addComponent(t)

        # --- picker: fires clicked() when the player clicks on the entity ---
        picker = QObjectPicker(entity)
        picker.setHoverEnabled(False)
        picker.setDragEnabled(False)
        picker.clicked.connect(
            lambda _event, e=entity: self._on_enemy_clicked(e)
        )
        entity.addComponent(picker)

        self._enemies[entity] = EnemyInfo(
            server=server,
            host_name=host_name,
            service_name=service_name,
            status=status,
            display_name=display_name,
        )

    # ------------------------------------------------------------------
    # Game events
    # ------------------------------------------------------------------

    def _on_enemy_clicked(self, entity: 'QEntity'):
        """Handle a player click on an enemy entity."""
        info = self._enemies.pop(entity, None)
        if info is None:
            return  # already killed

        # Hide the entity immediately (acknowledgement happens in background)
        entity.setEnabled(False)

        self._acknowledge(info)
        self._killed += 1
        self._update_score()
        self._show_message(f'💥  {info.display_name}  – acknowledged!')

    def _acknowledge(self, info: 'EnemyInfo'):
        """Send an acknowledgement to the monitoring server in a daemon thread."""
        from Nagstamon.config import conf

        server = info.server
        try:
            username = conf.servers[server.name].username or 'nagstamon-fps'
        except (AttributeError, KeyError):
            username = 'nagstamon-fps'

        info_dict = {
            'host': info.host_name,
            'service': info.service_name,
            'author': username,
            'comment': 'Acknowledged via Nagstamon FPS Mode',
            'sticky': True,
            'notify': True,
            'persistent': True,
            'acknowledge_all_services': False,
            'all_services': [],
        }

        def _do():
            try:
                server.set_acknowledge(info_dict)
            except Exception as exc:  # noqa: BLE001
                print(f'[Nagstamon FPS] acknowledge error: {exc}')

        Thread(target=_do, daemon=True).start()

    # ------------------------------------------------------------------
    # HUD helpers
    # ------------------------------------------------------------------

    def _update_score(self):
        remaining = len(self._enemies)
        self._score_label.setText(
            f'Problems: {remaining} remaining  ·  {self._killed} acknowledged'
        )
        self._score_label.adjustSize()

    def _show_message(self, text: str, duration_ms: int = 3500):
        self._msg_label.setText(text)
        self._reposition_overlays()
        self._msg_timer.start(duration_ms)

    def _clear_message(self):
        self._msg_label.setText('')


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

def show_fps_window(parent=None) -> Optional[NagstamonFPSWindow]:
    """Create and show the FPS window, or display an install hint if Qt3D is missing.

    Returns the :class:`NagstamonFPSWindow` instance, or ``None`` when Qt3D is
    not available.
    """
    if not QT3D_AVAILABLE:
        from PyQt6.QtWidgets import QMessageBox
        if _QT3D_IMPORT_ERROR:
            detail = (
                f'Error:\n    {_QT3D_IMPORT_ERROR}\n\n'
                'This usually means PyQt6 and PyQt6-3D are built against\n'
                'different Qt versions.  Install matching versions, e.g.:\n'
                '    pip install --upgrade PyQt6 PyQt6-3D'
            )
        else:
            detail = (
                'Please install the PyQt6-3D package:\n'
                '    pip install PyQt6-3D'
            )
        QMessageBox.warning(
            parent,
            'Nagstamon FPS Mode',
            f'Qt3D is not available.\n\n{detail}',
        )
        return None

    window = NagstamonFPSWindow(parent)
    window.show()
    return window
