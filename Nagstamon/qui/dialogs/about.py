# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2025 Henri Wahl <henri@nagstamon.de> et al.
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

from os import sep
from platform import python_version

from Nagstamon.config import (AppInfo,
                              RESOURCES)
from Nagstamon.qui.dialogs.dialog import Dialog
from Nagstamon.qui.qt import (QSvgWidget,
                              Qt,
                              QT_VERSION_STR)



class DialogAbout(Dialog):
    """
    About information dialog
    """

    def __init__(self):
        Dialog.__init__(self, 'dialog_about')
        # first add the logo on top - no idea how to achive in Qt Designer
        logo = QSvgWidget(f'{RESOURCES}{sep}nagstamon.svg')
        logo.setFixedSize(100, 100)
        self.window.vbox_about.insertWidget(1, logo, 0, Qt.AlignmentFlag.AlignHCenter)
        # update version information
        self.window.label_nagstamon.setText(f'<h1>{AppInfo.NAME} {AppInfo.VERSION}</h1>')
        self.window.label_nagstamon_long.setText('<h2>Nagios¹ status monitor for your desktop</2>')
        self.window.label_copyright.setText(AppInfo.COPYRIGHT)
        self.window.label_website.setText(f'<a href={AppInfo.WEBSITE}>{AppInfo.WEBSITE}</a>')
        self.window.label_website.setOpenExternalLinks(True)
        self.window.label_versions.setText(f'Python: {python_version()}, Qt: {QT_VERSION_STR}')
        self.window.label_contribution.setText(
            f'<a href={AppInfo.WEBSITE}/contribution>Contribution</a> | <a href=https://paypal.me/nagstamon>Donation</a>')
        self.window.label_footnote.setText('<small>¹ meanwhile many more monitors...</small>')

        # fill in license information
        license_file = open(f'{RESOURCES}{sep}LICENSE', encoding='utf-8')
        license_file_content = license_file.read()
        license_file.close()
        self.window.textedit_license.setPlainText(license_file_content)
        self.window.textedit_license.setReadOnly(True)

        # fill in credits information
        credits_file = open(f'{RESOURCES}{sep}CREDITS', encoding='utf-8')
        credits_file_content = credits_file.read()
        credits_file.close()
        self.window.textedit_credits.setText(credits_file_content)
        self.window.textedit_credits.setOpenExternalLinks(True)
        self.window.textedit_credits.setReadOnly(True)

        self.window.tabs.setCurrentIndex(0)
