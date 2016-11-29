#!/usr/bin/env python3
# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2016 Henri Wahl <h.wahl@ifw-dresden.de> et al.
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

import os
import platform
import sys
import argparse
import configparser
import base64
import zlib
import datetime
from collections import OrderedDict

# avoid build error because of debug_queue unknown to setup.py
# if anybody knows a more elegant way (which surely exists) let me know
# it had to work quickly!
# ##if not 'setup.py' in sys.argv[0] and not 'build.py' in sys.argv[0]:
# ##    # get debug queue from nagstamon.py
# ##    debug_queue = sys.modules['__main__'].debug_queue

# queue.Queue() needs threading module which might be not such a good idea to be used
# because QThread is already in use
# maybe not the most logical place here to be defined but at least all
# modules access Config.py so it can be distributed from here
debug_queue = list()

# temporary dict for string-to-bool-conversion
# the bool:bool relations are thought to make things easier in Dialog_Settings.ok()
BOOLPOOL = {'False': False,
            'True': True,
            False: False,
            True: True}

# needed when OS-specific decisions have to be made, mostly Linux/non-Linux
NON_LINUX = ('Darwin', 'Windows')


class AppInfo(object):

    """
        contains app information previously located in GUI.py
    """
    NAME = 'Nagstamon'
    VERSION = '2.1-20161130'
    WEBSITE = 'https://nagstamon.ifw-dresden.de'
    COPYRIGHT = '©2008-2016 Henri Wahl et al.'
    COMMENTS = 'Nagios status monitor for your desktop'
    # version URL depends on version string
    if 'alpha' in VERSION.lower() or\
       'beta' in VERSION.lower() or\
       'rc' in VERSION.lower() or\
       '-' in VERSION.lower():
        VERSION_URL = WEBSITE + '/version/unstable'
    else:
        VERSION_URL = WEBSITE + '/version/stable'


class Config(object):

    """
        The place for central configuration.
    """

    def __init__(self):
        """
            read config file and set the appropriate attributes
            supposed to be sensible defaults
        """
        # move from minute interval to seconds
        self.update_interval_seconds = 60
        self.short_display = False
        self.long_display = True
        self.show_tooltips = True
        self.show_grid = True
        self.grid_use_custom_intensity = False
        self.grid_alternation_intensity = 10
        self.highlight_new_events = True
        self.default_sort_field = 'status'
        self.default_sort_order = 'descending'
        self.filter_all_down_hosts = False
        self.filter_all_unreachable_hosts = False
        self.filter_all_flapping_hosts = False
        self.filter_all_unknown_services = False
        self.filter_all_warning_services = False
        self.filter_all_critical_services = False
        self.filter_all_flapping_services = False
        self.filter_acknowledged_hosts_services = False
        self.filter_hosts_services_disabled_notifications = False
        self.filter_hosts_services_disabled_checks = False
        self.filter_hosts_services_maintenance = False
        self.filter_services_on_acknowledged_hosts = False
        self.filter_services_on_down_hosts = False
        self.filter_services_on_hosts_in_maintenance = False
        self.filter_services_on_unreachable_hosts = False
        self.filter_hosts_in_soft_state = False
        self.filter_services_in_soft_state = False
        self.position_x = 30
        self.position_y = 30
        self.popup_details_hover = True
        self.popup_details_clicking = False
        self.close_details_hover = True
        self.close_details_clicking = False
        self.connect_by_host = True
        self.connect_by_dns = False
        self.connect_by_ip = False
        self.use_default_browser = True
        self.use_custom_browser = False
        self.custom_browser = ''
        self.debug_mode = False
        self.debug_to_file = False
        self.debug_file = os.path.expanduser('~') + os.sep + "nagstamon.log"
        self.check_for_new_version = True
        self.notification = True
        self.notification_flashing = True
        self.notification_desktop = False
        self.notification_actions = False
        self.notification_sound = True
        self.notification_sound_repeat = False
        self.notification_default_sound = True
        self.notification_custom_sound = False
        self.notification_custom_sound_warning = ''
        self.notification_custom_sound_critical = ''
        self.notification_custom_sound_down = ''
        self.notification_action_warning = False
        self.notification_action_warning_string = ''
        self.notification_action_critical = False
        self.notification_action_critical_string = ''
        self.notification_action_down = False
        self.notification_action_down_string = ''
        self.notification_action_ok = False
        self.notification_action_ok_string = ''
        self.notification_custom_action = False
        self.notification_custom_action_string = ''
        self.notification_custom_action_separator = ''
        self.notification_custom_action_single = False
        self.notify_if_up = False
        self.notify_if_warning = True
        self.notify_if_critical = True
        self.notify_if_unknown = True
        self.notify_if_unreachable = True
        self.notify_if_down = True
        # Regular expression filters
        self.re_host_enabled = False
        self.re_host_pattern = ''
        self.re_host_reverse = False
        self.re_service_enabled = False
        self.re_service_pattern = ''
        self.re_service_reverse = False
        self.re_status_information_enabled = False
        self.re_status_information_pattern = ''
        self.re_status_information_reverse = False
        self.color_ok_text = self.default_color_ok_text = '#FFFFFF'
        self.color_ok_background = self.default_color_ok_background = '#006400'
        self.color_warning_text = self.default_color_warning_text = "#000000"
        self.color_warning_background = self.default_color_warning_background = '#FFFF00'
        self.color_critical_text = self.default_color_critical_text = '#FFFFFF'
        self.color_critical_background = self.default_color_critical_background = '#FF0000'
        self.color_unknown_text = self.default_color_unknown_text = '#000000'
        self.color_unknown_background = self.default_color_unknown_background = '#FFA500'
        self.color_unreachable_text = self.default_color_unreachable_text = '#FFFFFF'
        self.color_unreachable_background = self.default_color_unreachable_background = '#8B0000'
        self.color_down_text = self.default_color_down_text = '#FFFFFF'
        self.color_down_background = self.default_color_down_background = '#000000'
        self.color_error_text = self.default_color_error_text = '#000000'
        self.color_error_background = self.default_color_error_background = '#D3D3D3'
        self.statusbar_floating = True
        self.icon_in_systray = False
        # ##self.appindicator = False
        self.fullscreen = False
        self.fullscreen_display = 0
        self.font = ''
        self.defaults_acknowledge_sticky = False
        self.defaults_acknowledge_send_notification = False
        self.defaults_acknowledge_persistent_comment = False
        self.defaults_acknowledge_all_services = False
        self.defaults_acknowledge_comment = 'acknowledged'
        self.defaults_submit_check_result_comment = 'check result submitted'
        self.defaults_downtime_duration_hours = 2
        self.defaults_downtime_duration_minutes = 0
        self.defaults_downtime_comment = 'scheduled downtime'
        self.defaults_downtime_type_fixed = True
        self.defaults_downtime_type_flexible = False
        # internal flag to determine if keyring is available at all - defaults to False
        # use_system_keyring is checked and defined some lines later after config file was read
        self.keyring_available = False
        # setting for keyring usage
        self.use_system_keyring = False

        # Special FX
        # Centreon
        self.re_criticality_enabled = False
        self.re_criticality_pattern = ''
        self.re_criticality_reverse = False

        # the app is unconfigured by default and will stay so if it
        # would not find a config file
        self.unconfigured = True

        # adding cli args variable
        self.cli_args = {}

        # Parse the command line
        parser = argparse.ArgumentParser(description='Nagstamon for your CLI')
        # might be not necessary anymore - to be tested
        # ##parser.add_argument('-psn', action='store_true',
        # ##    help='force ~/.nagstamon as config folder (used by launchd in MacOSX)')
        # necessary because otherwise setup.py goes crazy of argparse

        # separate NagstaCLI from
        if len(sys.argv) > 2 or (len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h']):
            parser.add_argument('--servername', type=str, help="name of the (Nagios)server. Look in nagstamon config")
            parser.add_argument('--hostname', type=str)
            parser.add_argument('--comment', type=str, default="")
            parser.add_argument('--service', type=str, default="", help="specify service, if needed. Mostly the whole host goes to downstate")
            parser.add_argument('--fixed', type=str, choices=['y', 'n'], default="y", help="fixed=n means wait for service/host to go down, then start the downtime")
            parser.add_argument('--start_time', type=str, help="start time for downtime")
            parser.add_argument('--hours', type=int, help="amount of hours for downtime")
            parser.add_argument('--minutes', type=int, help="amount of minutes for downtime")
            parser.add_argument('--config', type=str, help="Path for configuration folder")
            parser.add_argument('--output', type=str, choices=['y', 'n'], default="y", help="lists given parameter (for debugging)")
        else:
            parser.add_argument('config', nargs='?', help='Path for configuration folder')

        self.cli_args, unknown = parser.parse_known_args()

        # try to use a given config file - there must be one given
        # if sys.argv is larger than 1
        # ##if args.psn:
        # ##    # new configdir approach
        # ##    self.configdir = os.path.expanduser('~') + os.sep + '.nagstamon'
        # ##elif args.cfgpath:
        if len(sys.argv) < 3 and self.cli_args.config:
            # allow to give a config file
            self.configdir = self.cli_args.config

        # otherwise if there exits a configdir in current working directory it should be used
        elif os.path.exists(os.getcwd() + os.sep + 'nagstamon.config'):
            self.configdir = os.getcwd() + os.sep + 'nagstamon.config'
        else:
            # ~/.nagstamon/nagstamon.conf is the user conf file
            # os.path.expanduser('~') finds out the user HOME dir where
            # nagstamon expects its conf file to be
            self.configdir = os.path.expanduser('~') + os.sep + '.nagstamon'

        self.configfile = self.configdir + os.sep + 'nagstamon.conf'

        # make path fit for actual os, normcase for letters and normpath for path
        self.configfile = os.path.normpath(os.path.normcase(self.configfile))

        # because the name of the configdir is also stored in the configfile
        # there may be situations where the name gets overwritten by a
        # wrong name so it will be stored here temporarily
        configdir_temp = self.configdir

        # default settings dicts
        self.servers = dict()
        self.actions = dict()

        if os.path.exists(self.configfile):
            # instantiate a configparser to parse the conf file
            # SF.net bug #3304423 could be fixed with allow_no_value argument which
            # is only available since Python 2.7
            # since Python 3 '%' will be interpolated by default which crashes
            # with some URLs
            config = configparser.ConfigParser(allow_no_value=True, interpolation=None)
            config.read(self.configfile)

            # go through all sections of the conf file
            for section in config.sections():
                # go through all items of each sections (in fact there is only on
                # section which has to be there to comply to the .INI file standard

                for i in config.items(section):
                    # omit config file info as it makes no sense to store its path
                    if not i[0] in ('configfile', 'configdir'):
                        # create a key of every config item with its appropriate value
                        # check first if it is a bool value and convert string if it is
                        if i[1] in BOOLPOOL:
                            object.__setattr__(self, i[0], BOOLPOOL[i[1]])
                        # in case there are numbers intify them to avoid later conversions
                        # treat negative value specially as .isdecimal() will not detect it
                        elif i[1].isdecimal() or \
                                (i[1].startswith('-') and i[1].split('-')[1].isdecimal()):
                            object.__setattr__(self, i[0], int(i[1]))
                        else:
                            object.__setattr__(self, i[0], i[1])

            # because the switch from Nagstamon 1.0 to 1.0.1 brings the use_system_keyring property
            # and all the thousands 1.0 installations do not know it yet it will be more comfortable
            # for most of the Windows users if it is only defined as False after it was checked
            # from config file
            # if not self.__dict__.has_key("use_system_keyring"):
            if 'use_system_keyring' not in self.__dict__.keys():
                if self.unconfigured is True:
                    # an unconfigured system should start with no keyring to prevent crashes
                    self.use_system_keyring = False
                else:
                    # a configured system seemed to be able to run and thus use system keyring
                    if platform.system() in NON_LINUX:
                        self.use_system_keyring = True
                    else:
                        self.use_system_keyring = self.KeyringAvailable()

            # reset self.configdir to temporarily saved value in case it differs from
            # the one read from configfile and so it would fail to save next time
            self.configdir = configdir_temp

            # Servers configuration...
            self.servers = self._LoadServersMultipleConfig()
            # ... and actions
            self.actions = self.LoadMultipleConfig("actions", "action", "Action")

            # seems like there is a config file so the app is not unconfigured anymore
            self.unconfigured = False

        # Load actions if Nagstamon is not unconfigured, otherwise load defaults
        if self.unconfigured is True:
            self.actions = self._DefaultActions()

        # do some conversion stuff needed because of config changes and code cleanup
        self._LegacyAdjustments()

    def _LoadServersMultipleConfig(self):
        """
        load servers config - special treatment because of obfuscated passwords
        """
        self.keyring_available = self.KeyringAvailable()

        servers = self.LoadMultipleConfig('servers', 'server', 'Server')
        # deobfuscate username + password inside a try-except loop
        # if entries have not been obfuscated yet this action should raise an error
        # and old values (from nagstamon < 0.9.0) stay and will be converted when next
        # time saving config
        try:
            for server in servers:
                # usernames for monitor server and proxy
                servers[server].username = self.DeObfuscate(servers[server].username)
                servers[server].proxy_username = self.DeObfuscate(servers[server].proxy_username)
                # passwords for monitor server and proxy
                if servers[server].save_password == 'False':
                    servers[server].password = ""
                elif self.keyring_available and self.use_system_keyring:
                    # necessary to import on-the-fly due to possible Windows crashes
                    if platform.system() in NON_LINUX:
                        import keyring
                    else:
                        import Nagstamon.thirdparty.keyring as keyring
                    password = keyring.get_password('Nagstamon', '@'.join((servers[server].username,
                                                                           servers[server].monitor_url))) or ""
                    if password == "":
                        if servers[server].password != "":
                            servers[server].password = self.DeObfuscate(servers[server].password)
                    else:
                        servers[server].password = password
                elif servers[server].password != "":
                    servers[server].password = self.DeObfuscate(servers[server].password)
                # proxy password
                if self.keyring_available and self.use_system_keyring:
                    # necessary to import on-the-fly due to possible Windows crashes
                    if platform.system() in NON_LINUX:
                        import keyring
                    else:
                        import Nagstamon.thirdparty.keyring as keyring
                    proxy_password = keyring.get_password('Nagstamon', '@'.join(('proxy',
                                                                                 servers[server].proxy_username,
                                                                                 servers[server].proxy_address))) or ""
                    if proxy_password == "":
                        if servers[server].proxy_password != "":
                            servers[server].proxy_password = self.DeObfuscate(servers[server].proxy_password)
                    else:
                        servers[server].proxy_password = proxy_password
                elif servers[server].proxy_password != "":
                    servers[server].proxy_password = self.DeObfuscate(servers[server].proxy_password)

                # do only deobfuscating if any autologin_key is set - will be only Centreon
                if 'autologin_key' in servers[server].__dict__.keys():
                    if len(servers[server].__dict__['autologin_key']) > 0:
                        servers[server].autologin_key = self.DeObfuscate(servers[server].autologin_key)

                # only needed for those who used Icinga2 before it became IcingaWeb2
                if servers[server].type == 'Icinga2':
                    servers[server].type = 'IcingaWeb2'

        except Exception:
            import traceback
            traceback.print_exc(file=sys.stdout)

        return servers

    def LoadMultipleConfig(self, settingsdir, setting, configobj):
        """
            load generic config into settings dict and return to central config
        """
        # defaults as empty dict in case settings dir/files could not be found
        settings = OrderedDict()

        try:
            if os.path.exists(self.configdir + os.sep + settingsdir):
                for f in sorted(os.listdir(self.configdir + os.sep + settingsdir)):
                    if f.startswith(setting + '_') and f.endswith('.conf'):
                        config = configparser.ConfigParser(allow_no_value=True, interpolation=None)
                        config.read(self.configdir + os.sep + settingsdir + os.sep + f)

                        # create object for every setting
                        name = f.split('_', 1)[1].rpartition('.')[0]
                        settings[name] = globals()[configobj]()

                        # go through all items of the server
                        for i in config.items(setting + '_' + name):
                            # create a key of every config item with its appropriate value
                            if i[1] in BOOLPOOL:
                                value = BOOLPOOL[i[1]]
                            # in case there are numbers intify them to avoid later conversions
                            # treat negative value specially as .isdecimal() will not detect it
                            elif i[1].isdecimal() or \
                                    (i[1].startswith('-') and i[1].split('-')[1].isdecimal()):
                                value = int(i[1])
                            else:
                                value = i[1]
                            settings[name].__setattr__(i[0], value)
        except Exception:
            import traceback
            traceback.print_exc(file=sys.stdout)

        return settings

    def SaveConfig(self):
        """
            save config file
        """
        try:
            # Make sure .nagstamon is created
            if not os.path.exists(self.configdir):
                os.makedirs(self.configdir)
            # save config file with configparser
            config = configparser.ConfigParser(allow_no_value=True, interpolation=None)
            # general section for Nagstamon
            config.add_section('Nagstamon')
            for option in self.__dict__:
                if option not in ['servers', 'actions', 'configfile', 'configdir', 'cli_args']:
                    config.set('Nagstamon', option, str(self.__dict__[option]))

            # because the switch from Nagstamon 1.0 to 1.0.1 brings the use_system_keyring property
            # and all the thousands 1.0 installations do not know it yet it will be more comfortable
            # for most of the Windows users if it is only defined as False after it was checked
            # from config file
            if 'use_system_keyring' not in self.__dict__.keys():
                if self.unconfigured is True:
                    # an unconfigured system should start with no keyring to prevent crashes
                    self.use_system_keyring = False
                else:
                    # a configured system seemed to be able to run and thus use system keyring
                    if platform.system() in NON_LINUX:
                        self.use_system_keyring = True
                    else:
                        self.use_system_keyring = self.KeyringAvailable()

            # save actions dict
            self.SaveMultipleConfig('servers', 'server')

            # save actions dict
            self.SaveMultipleConfig('actions', 'action')

            # open, save and close config file
            f = open(os.path.normpath(self.configfile), "w")
            config.write(f)
            f.close()

            # debug
            if self.debug_mode:
                debug_queue.append('DEBUG: {0} Saving configuration to file {1}'.format(str(datetime.datetime.now()),
                    self.configfile))
        except Exception as err:
            import traceback
            traceback.print_exc(file=sys.stdout)
            # debug
            if self.debug_mode:
                debug_queue.append('ERROR: {0} {1} while saving configuration to file {2}'.format(str(datetime.datetime.now()),
                                                                                                  err,
                                                                                                  self.configfile))

    def SaveMultipleConfig(self, settingsdir, setting):
        """
            saves conf files for settings like actions in extra directories
            "multiple" means that multiple confs for actions or servers are loaded,
            not just one like for e.g. sound file
        """

        # only import keyring lib if configured to do so - to avoid Windows crashes
        # like https://github.com/HenriWahl/Nagstamon/issues/97
        if self.use_system_keyring is True:
            self.keyring_available = self.KeyringAvailable()

        # one section for each setting
        for s in self.__dict__[settingsdir]:
            config = configparser.ConfigParser(allow_no_value=True, interpolation=None)
            config.add_section(setting + '_' + s)
            for option in self.__dict__[settingsdir][s].__dict__:
                # obfuscate certain entries in config file - special arrangement for servers
                if settingsdir == 'servers':
                    if option in ['username', 'password', 'proxy_username', 'proxy_password', 'autologin_key']:
                        value = self.Obfuscate(self.__dict__[settingsdir][s].__dict__[option])
                        if option == 'password':
                            if self.__dict__[settingsdir][s].save_password is False:
                                value = ''
                            elif self.keyring_available and self.use_system_keyring:
                                if self.__dict__[settingsdir][s].password != '':
                                    # necessary to import on-the-fly due to possible Windows crashes
                                    if platform.system() in NON_LINUX:
                                        import keyring
                                    else:
                                        import Nagstamon.thirdparty.keyring as keyring
                                    # provoke crash if password saving does not work - this is the case
                                    # on newer Ubuntu releases
                                    try:
                                        keyring.set_password('Nagstamon', '@'.join((self.__dict__[settingsdir][s].username,
                                            self.__dict__[settingsdir][s].monitor_url)),
                                            self.__dict__[settingsdir][s].password)
                                    except Exception:
                                        import traceback
                                        traceback.print_exc(file=sys.stdout)
                                        sys.exit(1)
                                value = ''
                        if option == 'proxy_password':
                            if self.keyring_available and self.use_system_keyring:
                                # necessary to import on-the-fly due to possible Windows crashes
                                if platform.system() in NON_LINUX:
                                    import keyring
                                else:
                                    import Nagstamon.thirdparty.keyring as keyring
                                if self.__dict__[settingsdir][s].proxy_password != '':
                                    # provoke crash if password saving does not work - this is the case
                                    # on newer Ubuntu releases
                                    try:
                                        keyring.set_password('Nagstamon', '@'.join(('proxy',
                                            self.__dict__[settingsdir][s].proxy_username,
                                            self.__dict__[settingsdir][s].proxy_address)),
                                            self.__dict__[settingsdir][s].proxy_password)
                                    except Exception:
                                        import traceback
                                        traceback.print_exc(file=sys.stdout)
                                        sys.exit(1)

                                value = ''
                        config.set(setting + '_' + s, option, str(value))
                    else:
                        config.set(setting + '_' + s, option, str(self.__dict__[settingsdir][s].__dict__[option]))
                else:
                    config.set(setting + '_' + s, option, str(self.__dict__[settingsdir][s].__dict__[option]))

            # open, save and close config_server file
            if not os.path.exists(self.configdir + os.sep + settingsdir):
                os.makedirs(self.configdir + os.sep + settingsdir)
            f = open(os.path.normpath(self.configdir + os.sep + settingsdir + os.sep + setting + "_" + s + ".conf"), "w")
            config.write(f)
            f.close()

        # ### clean up old deleted/renamed config files
        # ##if os.path.exists(self.configdir + os.sep + settingsdir):
        # ##    for f in os.listdir(self.configdir + os.sep + settingsdir):
        # ##        if not f.split(setting + "_")[1].split(".conf")[0] in self.__dict__[settingsdir]:
        # ##            os.unlink(self.configdir + os.sep + settingsdir + os.sep + f)

    def KeyringAvailable(self):
        """
            determine if keyring module and an implementation is available for secure password storage
        """
        try:
            # Linux systems should use keyring only if it comes with the distro, otherwise chances are small
            # that keyring works at all
            if platform.system() in NON_LINUX:
                # safety first - if not yet available disable it
                if 'use_system_keyring' not in self.__dict__.keys():
                    self.use_system_keyring = False
                # only import keyring lib if configured to do so
                # necessary to avoid Windows crashes like https://github.com/HenriWahl/Nagstamon/issues/97
                if self.use_system_keyring is True:
                    # hint for packaging: nagstamon.spec always have to match module path
                    # keyring has to be bound to object to be used later
                    import keyring
                    return not (keyring.get_keyring() is None)
                else:
                    return False
            else:
                # keyring and secretstorage have to be importable
                import Nagstamon.thirdparty.keyring as keyring
                # import secretstorage module as dependency of keyring -
                # if not available keyring won't work
                import secretstorage 
                if ("SecretService") in dir(keyring.backends) and not (keyring.get_keyring() is None):
                    return True
        except Exception:
            import traceback
            traceback.print_exc(file=sys.stdout)
            return False

    def Obfuscate(self, string, count=5):
        """
            Obfuscate a given string to store passwords etc.
        """

        string = string.encode()

        for i in range(count):
            string = base64.b64encode(string).decode()
            string = list(string)
            string.reverse()
            string = "".join(string)
            string = string.encode()
            string = zlib.compress(string)

        # make unicode of bytes string
        string = base64.b64encode(string).decode()
        return string

    def DeObfuscate(self, string, count=5):
        """
            Deobfucate previously obfuscated string
        """
        string = base64.b64decode(string)

        for i in range(count):
            string = zlib.decompress(string)
            string = string.decode()
            string = list(string)
            string.reverse()
            string = "".join(string)
            string = base64.b64decode(string)

        # make unicode of bytes coming from base64 operations
        string = string.decode()

        return string

    def _DefaultActions(self):
        """
        create some default actions like SSH and so on
        """
        if platform.system() == "Windows":
            defaultactions = {"RDP": Action(name="RDP", description="Connect via RDP.",
                type="command", string="C:\windows\system32\mstsc.exe /v:$ADDRESS$"),
                "VNC": Action(name="VNC", description="Connect via VNC.",
                    type="command", string="C:\Program Files\TightVNC\vncviewer.exe $ADDRESS$"),
                "Telnet": Action(name="Telnet", description="Connect via Telnet.",
                    type="command", string="C:\Windows\System32\Telnet.exe root@$ADDRESS$"),
                "SSH": Action(name="SSH", description="Connect via SSH.",
                    type="command", string="C:\Program Files\PuTTY\putty.exe -l root $ADDRESS$")}
        elif platform.system() == "Darwin":
            defaultactions = {"RDP": Action(name="RDP", description="Connect via RDP.",
                type="command", string="open rdp://$ADDRESS$"),
                "VNC": Action(name="VNC", description="Connect via VNC.",
                    type="command", string="open vnc://$ADDRESS$"),
                "SSH": Action(name="SSH", description="Connect via SSH.",
                    type="command", string="open ssh://root@$ADDRESS$"),
                "Telnet": Action(name="Telnet", description="Connect via Telnet.",
                    type="command", string="open telnet://root@$ADDRESS$")}
        else:
            # the Linux settings
            defaultactions = {"RDP": Action(name="RDP", description="Connect via RDP.",
                type="command", string="/usr/bin/rdesktop -g 1024x768 $ADDRESS$"),
                "VNC": Action(name="VNC", description="Connect via VNC.",
                    type="command", string="/usr/bin/vncviewer $ADDRESS$"),
                "SSH": Action(name="SSH", description="Connect via SSH.",
                    type="command", string="/usr/bin/gnome-terminal -x ssh root@$ADDRESS$"),
                "Telnet": Action(name="Telnet", description="Connect via Telnet.",
                    type="command", string="/usr/bin/gnome-terminal -x telnet root@$ADDRESS$"),
                "Update-Linux": Action(name="Update-Linux", description="Run remote update script.",
                    type="command", string="/usr/bin/terminator -x ssh root@$HOST$ update.sh",
                    enabled=False)}
                # OS agnostic actions as examples
        defaultactions["Nagios-1-Click-Acknowledge-Host"] = Action(name="Nagios-1-Click-Acknowledge-Host", type="url",
                description="Acknowledges a host with one click.",
                filter_target_service=False, enabled=False,
                string="$MONITOR-CGI$/cmd.cgi?cmd_typ=33&cmd_mod=2&host=$HOST$\
                        &com_author=$USERNAME$&com_data=acknowledged&btnSubmit=Commit")
        defaultactions["Nagios-1-Click-Acknowledge-Service"] = Action(name="Nagios-1-Click-Acknowledge-Service", type="url",
                description="Acknowledges a service with one click.",
                filter_target_host=False, enabled=False,
                string="$MONITOR-CGI$/cmd.cgi?cmd_typ=34&cmd_mod=2&host=$HOST$\
                        &service=$SERVICE$&com_author=$USERNAME$&com_data=acknowledged&btnSubmit=Commit")
        defaultactions["Opsview-Graph-Service"] = Action(name="Opsview-Graph-Service", type="browser",
                description="Show graph in browser.", filter_target_host=False,
                string="$MONITOR$/graph?service=$SERVICE$&host=$HOST$", enabled=False)
        defaultactions["Opsview-History-Host"] = Action(name="Opsview-Host-Service", type="browser",
                description="Show host in browser.", filter_target_host=True,
                string="$MONITOR$/event?host=$HOST$", enabled=False)
        defaultactions["Opsview-History-Service"] = Action(name="Opsview-History-Service", type="browser",
                description="Show history in browser.", filter_target_host=True,
                string="$MONITOR$/event?host=$HOST$&service=$SERVICE$", enabled=False)
        defaultactions["Check_MK-1-Click-Acknowledge-Host"] = Action(name="Check_MK-1-Click-Acknowledge-Host", type="url",
                description="Acknowledges a host with one click.",
                filter_target_service=False, enabled=False,
                string="$MONITOR$/view.py?_transid=$TRANSID$&_do_actions=yes&_do_confirm=Yes!&output_format=python&view_name=hoststatus&host=$HOST$&_ack_comment=$COMMENT-ACK$&_acknowledge=Acknowledge")
        defaultactions["Check_MK-1-Click-Acknowledge-Service"] = Action(name="Check_MK-1-Click-Acknowledge-Service", type="url",
                description="Acknowledges a host with one click.",
                filter_target_host=False, enabled=False,
                string="$MONITOR$/view.py?_transid=$TRANSID$&_do_actions=yes&_do_confirm=Yes!&output_format=python&view_name=service&host=$HOST$&_ack_comment=$COMMENT-ACK$&_acknowledge=Acknowledge&service=$SERVICE$")
        defaultactions["Check_MK Edit host in WATO"] = Action(name="Check_MK Edit host in WATO", enabled=False,
                monitor_type="Check_MK Multisite",
                description="Edit host in WATO.",
                string="$MONITOR$index.py?start_url=%2Fmonitor%2Fcheck_mk%2Fwato.py%3Fhost%3D$HOST$%26mode%3Dedit_host")
        defaultactions["Email"] = Action(name="Email", enabled=False, description="Send email to someone.", type="browser",
                string="mailto:servicedesk@my.org?subject=Monitor alert: $HOST$ - $SERVICE$ - $STATUS-INFO$&body=Please help!.%0d%0aBest regards from Nagstamon")

        return defaultactions

    def _LegacyAdjustments(self):
        # mere cosmetics but might be more clear for future additions - changing any "nagios"-setting to "monitor"
        for s in self.servers.values():
            if 'nagios_url' in s.__dict__.keys():
                s.monitor_url = s.nagios_url
            if 'nagios_cgi_url' in s.__dict__.keys():
                s.monitor_cgi_url = s.nagios_cgi_url

            # to reduce complexity in Centreon there is also only one URL necessary
            if s.type == "Centreon":
                s.monitor_url = s.monitor_cgi_url

        # switch to update interval in seconds not minutes
        if 'update_interval' in self.__dict__.keys():
            self.update_interval_seconds = int(self.update_interval) * 60
            self.__dict__.pop('update_interval')

        # remove support for GNOME2-trayicon-egg-stuff
        if 'statusbar_systray' in self.__dict__.keys():
            if self.statusbar_systray is True:
                self.icon_in_systray = True
            self.__dict__.pop('statusbar_systray')

        # some legacy action settings might need a little fix
        for action in self.actions.values():
            if not action.type.lower() in ('browser', 'command', 'url'):
                # set browser as default to make user notice something is wrong
                action.type = 'browser'

    def GetNumberOfEnabledMonitors(self):
        """
            returns the number of enabled monitors - in case all are disabled there is no need to display the popwin
        """
        # to be returned
        number = 0
        for server in self.servers.values():
            # ##if str(server.enabled) == "True":
            if server.enabled is True:
                number += 1
        return number

    def delete_file(self, settings_dir, settings_file):
        """
            delete specified .conf file if setting is deleted in GUI
        """
        # clean up old deleted/renamed config file
        file = os.path.abspath('{1}{0}{2}{0}{3}.conf'.format(os.sep, self.configdir, settings_dir, settings_file))
        if os.path.exists(file) and (os.path.isfile(file) or os.path.islink(file)):
            try:
                os.unlink(file)
            except Exception:
                import traceback
                traceback.print_exc(file=sys.stdout)


class Server(object):

    """
    one Server realized as object for config info
    """

    def __init__(self):
        self.enabled = True
        self.type = 'Nagios'
        self.name = 'Monitor server'
        self.monitor_url = 'https://monitor-server'
        self.monitor_cgi_url = 'https://monitor-server/monitor/cgi-bin'
        self.username = 'username'
        self.password = 'password'
        self.save_password = False
        self.use_proxy = False
        self.use_proxy_from_os = False
        self.proxy_address = 'http://proxyserver:port/'
        self.proxy_username = 'proxyusername'
        self.proxy_password = 'proxypassword'
        # defaults to 'basic', another possible value at the moment is 'digest'
        self.authentication = 'basic'
        self.timeout = 10
        # just GUI-wise deciding if more options are shown in server dialog
        self.show_options = False

        # special FX
        # Centreon autologin
        self.use_autologin = False
        self.autologin_key = ''

        # Icinga "host_display_name" instead of "host"
        self.use_display_name_host = False
        self.use_display_name_service = False

        # IcingaWeb2 might authenticate without cookies too - default is WITH cookies
        self.no_cookie_auth = False

        # Check_MK Multisite
        # Force Check_MK livestatus code to set AuthUser header for users who
        # are permitted to see all objects.
        self.force_authuser = False

        # OP5 api filters
        self.host_filter = 'state !=0'
        self.service_filter = 'state !=0 or host.state != 0'

class Action(object):

    """
    class for custom actions, which whill be thrown into one config dictionary like the servers
    """

    def __init__(self, **kwds):
        # to be or not to be enabled...
        self.enabled = True
        # monitor type
        self.monitor_type = ""
        # one of those: browser, url or command
        self.type = "browser"
        # thy name is...
        self.name = "Custom action"
        # OS of host where Nagstamon runs - especially commands are mostly not platform agnostic
        self.os = ""
        # description
        self.description = "Starts a custom action."
        # might be URL in case of type browser/url and a commandline for commands
        self.string = ""
        # version - maybe in future this might be more sophisticated
        self.version = "1"
        # kind of Nagios item this action is targeted to - maybe also usable for states
        self.filter_target_host = True
        self.filter_target_service = True
        # action applies only to certain hosts or services
        self.re_host_enabled = False
        self.re_host_pattern = ""
        self.re_host_reverse = False
        self.re_service_enabled = False
        self.re_service_pattern = ""
        self.re_service_reverse = False
        self.re_status_information_enabled = False
        self.re_status_information_pattern = ""
        self.re_status_information_reverse = False
        # close powin or not, depends on personal preference
        self.close_popwin = True
        self.leave_popwin_open = False
        # do an immediate recheck after action was applied
        self.recheck = False

        # special FX
        # Centreon criticality and autologin
        self.re_criticality_enabled = False
        self.re_criticality_pattern = ""
        self.re_criticality_reverse = False

        # add and/or all keywords to object
        for k in kwds:
            self.__dict__[k] = kwds[k]


# Initialize configuration to be accessed globally
conf = Config()

# try to get resources path if nagstamon got be installed by setup.py
RESOURCES = ""

try:
    # first try to find local resources directory in case Nagstamon was frozen with cx-Freeze for OSX or Windows
    executable_dir = os.path.join(os.sep.join(sys.executable.split(os.sep)[:-1]))
    if os.path.exists(os.path.normcase(os.sep.join((executable_dir, "resources")))):
        RESOURCES = os.path.normcase(os.sep.join((executable_dir, "resources")))
    else:
        import pkg_resources
        RESOURCES = pkg_resources.resource_filename("Nagstamon", "resources")

except Exception as err:
    # get resources directory from current directory - only if not being set before by pkg_resources
    # try-excepts necessary for platforms like Windows .EXE
    paths_to_check = [os.path.normcase(os.path.join(os.getcwd(), "Nagstamon", "resources")),
            os.path.normcase(os.path.join(os.getcwd(), "resources"))]
    try:
        # if resources dir is not available in CWD, try the
        # libs dir (site-packages) for the current Python
        from distutils.sysconfig import get_python_lib
        paths_to_check.append(os.path.normcase(os.path.join(get_python_lib(), "Nagstamon", "resources")))
    except Exception:
        pass

    # if we're still out of luck, maybe this was a user scheme install
    try:
        import site
        site.getusersitepackages()  # make sure USER_SITE is set
        paths_to_check.append(os.path.normcase(os.path.join(site.USER_SITE, "Nagstamon", "resources")))
    except Exception:
        pass

    # add directory nagstamon.py where nagstamon.py resides for cases like 0install without installed pkg-resources
    paths_to_check.append(os.sep.join(sys.argv[0].split(os.sep)[:-1] + ["Nagstamon", "resources"]))

    for path in paths_to_check:
        if os.path.exists(path):
            RESOURCES = path
            break
