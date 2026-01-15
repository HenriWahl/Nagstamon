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

from Nagstamon.config import AppInfo
from Nagstamon.qui.qt import (QMessageBox,
                              QObject,
                              Qt,
                              QThread,
                              QWidget,
                              Signal,
                              Slot)
from Nagstamon.servers import get_enabled_servers


class CheckVersion(QObject):
    """
    checking for updates
    """

    is_checking = False

    version_info_retrieved = Signal()

    @Slot(bool, QWidget)
    def check(self, start_mode=False, parent=None):

        if not self.is_checking:

            # lock checking thread
            self.is_checking = True

            # list of enabled servers which connections outside should be used to check
            self.enabled_servers = get_enabled_servers()

            # set mode to be evaluated by worker
            self.start_mode = start_mode

            # store caller of dialog window - not if at start because this will disturb EWMH
            if start_mode:
                self.parent = None
            else:
                self.parent = parent

            # thread for worker to avoid
            self.worker_thread = QThread(parent=self)
            self.worker = self.Worker(start_mode)

            # if update check is ready it sends the message to GUI thread
            self.worker.ready.connect(self.show_message)

            # stop thread if worker has finished
            self.worker.finished.connect(self.worker_thread.quit)
            # reset checking lock if finished
            self.worker.finished.connect(self.reset_checking)

            self.worker.moveToThread(self.worker_thread)
            # run check when thread starts
            self.worker_thread.started.connect(self.worker.check)
            self.worker_thread.start(QThread.Priority.LowestPriority)

    @Slot()
    def reset_checking(self):
        """
        reset checking the flag to avoid QThread crashes
        """
        self.is_checking = False

    @Slot(str)
    def show_message(self, message):
        """
        message dialog must be shown from GUI thread
        """
        self.version_info_retrieved.emit()

        # attempt to solve https://github.com/HenriWahl/Nagstamon/issues/303
        # might be working this time
        parent = self.parent

        messagebox = QMessageBox(QMessageBox.Icon.Information,
                                 'Nagstamon version check',
                                 message,
                                 QMessageBox.StandardButton.Ok,
                                 parent,
                                 Qt.WindowType.Dialog | Qt.WindowType.MSWindowsFixedSizeDialogHint)
        messagebox.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        messagebox.setWindowModality(Qt.WindowModality.NonModal)
        messagebox.open()

    class Worker(QObject):

        """
        check for a new version in the background
        """
        # send signal if some version information is available
        ready = Signal(str)

        finished = Signal()

        def __init__(self, start_mode=False):
            QObject.__init__(self)
            self.start_mode = start_mode

        def check(self):
            """
            check for update using server connection
            """
            # get servers to be used for checking the version
            enabled_servers = get_enabled_servers()

            # default latest version is 'unavailable' and message empty
            latest_version = 'unavailable'
            message = ''

            # find at least one server which allows getting version information
            for server in enabled_servers:
                for download_server, download_url in AppInfo.DOWNLOAD_SERVERS.items():
                    # dummy message just in case version check does not work
                    message = 'Cannot reach version check at <a href={0}>{0}</<a>.'.format(
                        f'https://{download_server}{AppInfo.VERSION_PATH}')

                    # retrieve VERSION_URL without auth information
                    response = server.fetch_url(f'https://{download_server}{AppInfo.VERSION_PATH}',
                                                giveback='raw',
                                                no_auth=True)

                    # stop searching the available download URLs
                    if response.error == '' and \
                            not response.result.startswith('<') and \
                            not '\n' in response.result and \
                            5 < len(response.result) < 15 and \
                            response.result[0].isdigit():
                        latest_version = response.result.strip()
                        break

                # ignore TLS error in case it was caused by requesting the latest version - not important for monitoring
                server.tls_error = False

                # stop searching via enabled servers
                if response.error == '' and not response.result.startswith('<'):
                    latest_version = response.result.strip()
                    break

            # compose a message according to version information
            if latest_version != 'unavailable':
                if latest_version == AppInfo.VERSION:
                    message = f'You are using the latest version <b>Nagstamon {AppInfo.VERSION}</b>.'
                # avoid GitHub HTML being evaluated as version number -> checking for length
                elif latest_version > AppInfo.VERSION and not len(latest_version) > 20:
                    message = f'The new version <b>Nagstamon {latest_version}</b> is available.<p>' \
                              f'Get it at <a href={AppInfo.WEBSITE}/download>{AppInfo.WEBSITE}/download</a>.'
                elif latest_version < AppInfo.VERSION:
                    # for some reason, the local version is newer than that remote one - just ignore
                    message = ''

            # check if there is anything to tell
            if message != '':
                # if run from startup do not cry if any error occurred or nothing new is available
                if self.start_mode is False or \
                        (self.start_mode is True and latest_version not in ('unavailable', AppInfo.VERSION)):
                    self.ready.emit(message)

            # tell thread to finish
            self.finished.emit()


# initialized an object to be used in other modules
check_version = CheckVersion()
