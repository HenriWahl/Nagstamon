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
import threading

from Nagstamon.config import (conf,
                              OS,
                              OS_MACOS)
from Nagstamon.cookies import save_oidc_tokens
from Nagstamon.qui.constants import (HEADERS,
                                     HEADERS_KEYS_COLUMNS,
                                     HEADERS_HEADERS_COLUMNS,
                                     SORT_ORDER,
                                     SPACE)
from Nagstamon.qui.qt import (QPushButton,
                              QSizePolicy,
                              Qt,
                              QVBoxLayout,
                              Signal,
                              Slot)
from Nagstamon.qui.widgets.buttons import (Button,
                                           PushButtonBrowserURL)
from Nagstamon.qui.widgets.labels import (ClosingLabel,
                                          ServerStatusLabel)
from Nagstamon.qui.widgets.layout import HBoxLayout
from Nagstamon.qui.widgets.treeview import TreeView
from Nagstamon.thirdparty.oidc_auth import (
    discover_oidc_from_icingaweb2,
    OIDCAuthenticator,
    OIDCError,
)


class ServerVBox(QVBoxLayout):
    """
    one VBox per server containing buttons and hosts/services listview
    """
    # used to update status label text like 'Connected-'
    change_label_status = Signal(str, str)

    # signal to submit server to authentication dialog for credentials
    authenticate_credentials = Signal(str)

    # signal to submit server to weblogin dialog as browser
    authenticate_weblogin = Signal(str)

    # handle TLS error button
    button_fix_tls_error_show = Signal()
    button_fix_tls_error_hide = Signal()

    # buttons pressed, which need dialogs
    button_edit_pressed = Signal(str)
    button_fix_tls_error_pressed = Signal(str, bool)

    # open dialog - may need closing the statuswindow
    open_dialog = Signal()

    # signals for thread-safe OIDC UI updates from background thread
    _oidc_status_update = Signal(str)
    _oidc_auth_finished = Signal()

    def __init__(self, server, parent=None):
        QVBoxLayout.__init__(self, parent)

        self.parent_statuswindow = parent

        # no space around
        self.setSpacing(0)
        self.setContentsMargins(0, 0, 0, 0)

        # server the vbox belongs to
        self.server = server

        # header containing monitor name, buttons and status
        self.header = HBoxLayout(spacing=SPACE, parent=parent)
        self.addLayout(self.header)
        # top and bottom should be kept by padding
        self.header.setContentsMargins(0, 0, SPACE, 0)

        self.label = ClosingLabel(parent=parent)
        self.label.mouse_released.connect(self.parent_statuswindow.hide_window)
        self.update_label()
        self.button_monitor = PushButtonBrowserURL(text='Monitor',
                                                   parent=parent,
                                                   server=self.server,
                                                   url_type='monitor')
        self.button_monitor.webbrowser_opened.connect(self.parent_statuswindow.hide_window)
        self.button_hosts = PushButtonBrowserURL(text='Hosts',
                                                 parent=parent,
                                                 server=self.server,
                                                 url_type='hosts')
        self.button_hosts.webbrowser_opened.connect(self.parent_statuswindow.hide_window)
        self.button_services = PushButtonBrowserURL(text='Services',
                                                    parent=parent,
                                                    server=self.server,
                                                    url_type='services')
        self.button_services.webbrowser_opened.connect(self.parent_statuswindow.hide_window)
        self.button_history = PushButtonBrowserURL(text='History',
                                                   parent=parent,
                                                   server=self.server,
                                                   url_type='history')
        self.button_history.webbrowser_opened.connect(self.parent_statuswindow.hide_window)
        self.button_edit = Button('Edit',
                                  parent=parent)

        # use label instead of spacer to be clickable
        self.label_stretcher = ClosingLabel('', parent=parent)
        self.label_stretcher.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Expanding)
        self.label_stretcher.mouse_released.connect(self.parent_statuswindow.hide_window)

        self.label_status = ServerStatusLabel(parent=parent)
        self.label_status.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.button_authenticate = QPushButton('Authenticate', parent=parent)

        self.button_oidc_auth = QPushButton('Authenticate', parent=parent)

        self.button_fix_tls_error = QPushButton('Fix error', parent=parent)

        # avoid useless spaces in macOS when server has nothing to show
        # see https://bugreports.qt.io/browse/QTBUG-2699
        self.button_monitor.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)
        self.button_history.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)
        self.button_services.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)
        self.button_hosts.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)
        self.button_edit.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)
        self.button_authenticate.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)
        self.button_oidc_auth.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)
        self.button_fix_tls_error.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)

        self.button_monitor.clicked.connect(self.button_monitor.open_url)
        self.button_hosts.clicked.connect(self.button_hosts.open_url)
        self.button_services.clicked.connect(self.button_services.open_url)
        self.button_history.clicked.connect(self.button_history.open_url)
        self.button_edit.clicked.connect(self.edit_server)

        self.header.addWidget(self.label)
        self.header.addWidget(self.button_monitor)
        self.header.addWidget(self.button_hosts)
        self.header.addWidget(self.button_services)
        self.header.addWidget(self.button_history)
        self.header.addWidget(self.button_edit)

        self.header.addWidget(self.label_stretcher)

        self.header.addWidget(self.label_status)
        self.header.addWidget(self.button_oidc_auth)
        self.header.addWidget(self.button_authenticate)
        self.header.addWidget(self.button_fix_tls_error)

        self.open_dialog.connect(self.parent_statuswindow.hide_window)

        # attempt to get header strings
        try:
            # when stored as simple lowercase keys
            sort_column = HEADERS_KEYS_COLUMNS[conf.default_sort_field]
        except Exception:
            # when as legacy stored as presentation string
            sort_column = HEADERS_HEADERS_COLUMNS[conf.default_sort_field]

        # convert sort order to number as used in Qt.SortOrder
        sort_order = SORT_ORDER[conf.default_sort_order.lower()]

        self.table = TreeView(len(HEADERS) + 1, 0, sort_column, sort_order, self.server, parent=parent)

        # delete vbox if thread quits
        self.table.worker_thread.finished.connect(self.delete)

        # connect worker to status label to reflect connectivity
        self.table.worker.change_label_status.connect(self.label_status.change)
        self.table.worker.restore_label_status.connect(self.label_status.restore)
        self.table.worker.authentication_needed.connect(self.parent_statuswindow.show_window_for_authentication)

        # care about authentications
        self.button_authenticate.clicked.connect(self.authenticate_server)
        self.button_oidc_auth.clicked.connect(self.oidc_auth_server)
        # thread-safe OIDC UI updates
        self._oidc_status_update.connect(self.label_status.setText)
        self._oidc_auth_finished.connect(self._on_oidc_auth_finished)
        # somehow a long way to connect the signal with the slot but works
        self.authenticate_credentials.connect(self.parent_statuswindow.injected_dialogs.authentication.show_auth_dialog)
        self.authenticate_weblogin.connect(self.parent_statuswindow.injected_dialogs.weblogin.show_browser)
        self.parent_statuswindow.injected_dialogs.authentication.update.connect(self.update_label)

        # start ignoring TLS trouble when button clicked
        self.button_fix_tls_error.clicked.connect(self.fix_tls_error)

        # connect button signals to dialogs
        self.button_edit_pressed.connect(self.parent_statuswindow.injected_dialogs.server.edit)
        self.button_fix_tls_error_pressed.connect(self.parent_statuswindow.injected_dialogs.server.edit)

        self.addWidget(self.table, 1)

        # as default do not show anything
        self.show_only_header()

    def get_real_height(self):
        """
        return summarized real height of hbox items and table
        """
        height = self.table.get_real_height()
        if self.label.isVisible() and self.button_monitor.isVisible():
            # compare item heights, decide to take the largest and add 2 time the MARGIN (top and bottom)
            if self.label.sizeHint().height() > self.button_monitor.sizeHint().height():
                height += self.label.sizeHint().height() + 2
            else:
                height += self.button_monitor.sizeHint().height() + 2
        return height

    @Slot()
    def show_all(self):
        """
        show all items in server vbox
        """
        self.button_authenticate.hide()
        self.button_oidc_auth.hide()
        self.button_edit.show()
        self.button_fix_tls_error.hide()
        self.button_history.show()
        self.button_hosts.show()
        self.button_monitor.show()
        self.button_services.show()
        self.label.show()
        self.label_status.show()
        self.label_stretcher.show()
        # special table treatment
        self.table.show()
        # self.table.is_shown = True

    @Slot()
    def show_only_header(self):
        """
        show all items in server vbox except the table - not needed if empty or major connection problem
        """
        self.button_authenticate.hide()
        self.button_oidc_auth.hide()
        self.button_edit.show()
        self.button_history.show()
        self.button_hosts.show()
        self.button_fix_tls_error.hide()
        self.button_monitor.show()
        self.button_services.show()
        self.label.show()
        self.label_status.show()
        self.label_stretcher.show()
        # special table treatment
        self.table.hide()

    @Slot()
    def hide_all(self):
        """
        hide all items in server vbox
        """
        self.button_authenticate.hide()
        self.button_oidc_auth.hide()
        self.button_edit.hide()
        self.button_fix_tls_error.hide()
        self.button_history.hide()
        self.button_hosts.hide()
        self.button_monitor.hide()
        self.button_services.hide()
        self.label.hide()
        self.label_status.hide()
        self.label_stretcher.hide()
        # special table treatment
        self.table.hide()

    @Slot()
    def delete(self):
        """
        delete VBox and its children
        """
        for widget in (self.label,
                       self.button_monitor,
                       self.button_hosts,
                       self.button_services,
                       self.button_history,
                       self.button_edit,
                       self.label_status,
                       self.label_stretcher,
                       self.button_authenticate,
                       self.button_oidc_auth,
                       self.button_fix_tls_error):
            widget.hide()
            widget.deleteLater()
        self.removeItem(self.header)
        self.header.deleteLater()
        self.table.hide()
        self.table.deleteLater()
        self.deleteLater()

    def edit_server(self):
        """
        call dialogs.server.edit() with server name
        """
        if not conf.fullscreen and not conf.windowed:
            self.open_dialog.emit()
        self.button_edit_pressed.emit(self.server.name)

    def authenticate_server(self):
        """
        send signal to open authentication dialog with self.server.name
        """
        if self.server.authentication == 'oidc':
            # OIDC needs the server settings dialog (with its Authenticate button), not a password prompt
            self.button_edit_pressed.emit(self.server.name)
        elif self.server.authentication != 'web':
            self.authenticate_credentials.emit(self.server.name)
        else:
            self.authenticate_weblogin.emit(self.server.name)

    def _iter_sibling_vboxes(self):
        """Yield all ServerVBox siblings from the status window."""
        for child in self.parent_statuswindow.servers_vbox.children():
            if isinstance(child, ServerVBox):
                yield child

    def _on_oidc_auth_finished(self):
        """Re-enable all OIDC Auth buttons after auth completes."""
        for vbox in self._iter_sibling_vboxes():
            if vbox.server.authentication == 'oidc':
                vbox.button_oidc_auth.setEnabled(True)

    def oidc_auth_server(self):
        """
        Directly trigger OIDC authentication flow from the status window
        """
        monitor_url = self.server.monitor_url
        if not monitor_url:
            return

        server_name = self.server.name
        server_conf = conf.servers.get(server_name)
        client_id = getattr(server_conf, 'oidc_client_id', 'nagstamon') if server_conf else 'nagstamon'
        redirect_port = getattr(server_conf, 'oidc_redirect_port', 12345) if server_conf else 12345

        self.button_oidc_auth.setEnabled(False)
        self._oidc_status_update.emit('Discovering OIDC endpoints...')

        # Disable all other OIDC Auth buttons to prevent concurrent auth flows
        # (concurrent flows would fail because the callback port is already in use)
        for vbox in self._iter_sibling_vboxes():
            if vbox is not self and vbox.server.authentication == 'oidc':
                vbox.button_oidc_auth.setEnabled(False)

        def _run():
            try:
                import requests
                if conf.debug_mode:
                    print(f'[OIDC] StatusWindow: Starting OIDC discovery for {monitor_url}')
                session = requests.Session()
                session.verify = not self.server.ignore_cert
                oidc_config = discover_oidc_from_icingaweb2(monitor_url, session, timeout=15)

                if conf.debug_mode:
                    print(f'[OIDC] StatusWindow: Discovery OK: token_endpoint={oidc_config["token_endpoint"]}')

                self._oidc_status_update.emit('Waiting for browser login...')

                authenticator = OIDCAuthenticator(
                    authorization_endpoint=oidc_config['authorization_endpoint'],
                    token_endpoint=oidc_config['token_endpoint'],
                    client_id=client_id,
                    redirect_port=redirect_port,
                )
                token_result = authenticator.authenticate(timeout=120)

                # Persist tokens so the server picks them up on next session creation
                save_oidc_tokens(server_name, {
                    'access_token': token_result.access_token,
                    'refresh_token': token_result.refresh_token or '',
                    'id_token': token_result.id_token or '',
                    'expires_at': token_result.expires_at,
                    'token_endpoint': oidc_config.get('token_endpoint', ''),
                    'authorization_endpoint': oidc_config.get('authorization_endpoint', ''),
                    'client_id': client_id,
                })

                # Reset the server's HTTP session so it reloads fresh tokens
                self.server.reset_http()

                if conf.debug_mode:
                    import time as _time
                    remaining = token_result.expires_at - _time.time()
                    print(f'[OIDC] StatusWindow: Authentication successful! '
                          f'expires_in={remaining:.0f}s, has_refresh={bool(token_result.refresh_token)}')
                self._oidc_status_update.emit('Authenticated successfully!')
            except OIDCError as e:
                if conf.debug_mode:
                    print(f'[OIDC] StatusWindow: OIDCError: {e}')
                self._oidc_status_update.emit(f'Error: {e}')
            except Exception as e:
                if conf.debug_mode:
                    import traceback
                    print(f'[OIDC] StatusWindow: Unexpected error: {e}')
                    traceback.print_exc()
                self._oidc_status_update.emit(f'Error: {e}')
            finally:
                self._oidc_auth_finished.emit()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    @Slot()
    def update_label(self):
        if self.server.authentication != 'web':
            self.label.setText(f'<big><b>&nbsp;{self.server.username}@{self.server.name}</b></big>')
        else:
            self.label.setText(f'<big><b>&nbsp;{self.server.name}</b></big>')
        # let label padding keep top and bottom space - apparently not necessary on OSX
        if OS != OS_MACOS:
            self.label.setStyleSheet('''padding-top: {0}px;
                                        padding-bottom: {0}px;'''.format(SPACE))

    @Slot()
    def fix_tls_error(self):
        """
        call dialogs.server.edit() with server name and showing extra options
        """
        if not conf.fullscreen and not conf.windowed:
            self.open_dialog.emit()
        self.button_fix_tls_error_pressed.emit(self.server.name, True)