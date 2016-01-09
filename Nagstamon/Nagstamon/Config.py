# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2014 Henri Wahl <h.wahl@ifw-dresden.de> et al.
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
import ConfigParser
import base64
import zlib


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
        self.show_grid = True
        self.show_tooltips = True
        self.highlight_new_events = True
        self.default_sort_field = "Status"
        self.default_sort_order = "Descending"
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
        self.notification_custom_sound_warning = None
        self.notification_custom_sound_critical = None
        self.notification_custom_sound_down = None
        self.notification_action_warning = False
        self.notification_action_warning_string = ""
        self.notification_action_critical = False
        self.notification_action_critical_string = ""
        self.notification_action_down = False
        self.notification_action_down_string = ""
        self.notification_action_ok = False
        self.notification_action_ok_string = ""
        self.notification_custom_action = False
        self.notification_custom_action_string = False
        self.notification_custom_action_separator = False
        self.notification_custom_action_single = False
        self.notify_if_warning = True
        self.notify_if_critical = True
        self.notify_if_unknown = True
        self.notify_if_unreachable = True
        self.notify_if_down = True
        """
        # not yet working
        # Check_MK show-only-my-problems-they-are-way-enough feature
        self.only_my_issues = False
        """
        # Regular expression filters
        self.re_host_enabled = False
        self.re_host_pattern = ""
        self.re_host_reverse = False
        self.re_service_enabled = False
        self.re_service_pattern = ""
        self.re_service_reverse = False
        self.re_status_information_enabled = False
        self.re_status_information_pattern = ""
        self.re_status_information_reverse = False
        self.color_ok_text = self.default_color_ok_text = "#FFFFFF"
        self.color_ok_background = self.default_color_ok_background = "#006400"
        self.color_warning_text = self.default_color_warning_text = "#000000"
        self.color_warning_background = self.default_color_warning_background = "#FFFF00"
        self.color_critical_text = self.default_color_critical_text = "#FFFFFF"
        self.color_critical_background = self.default_color_critical_background = "#FF0000"
        self.color_unknown_text = self.default_color_unknown_text = "#000000"
        self.color_unknown_background = self.default_color_unknown_background = "#FFA500"

        self.color_information_text = self.default_color_warning_text = "#000000"
        self.color_information_background = self.default_color_warning_background = "#D6F6FF"
        self.color_high_text = self.default_color_critical_text = "#000000"
        self.color_high_background = self.default_color_critical_background = "#FF9999"
        self.color_average_text = self.default_color_critical_text = "#000000"
        self.color_average_background = self.default_color_critical_background = "#FFB689"

        self.color_unreachable_text = self.default_color_unreachable_text = "#FFFFFF"
        self.color_unreachable_background = self.default_color_unreachable_background = "#8B0000"
        self.color_down_text = self.default_color_down_text = "#FFFFFF"
        self.color_down_background = self.default_color_down_background = "#000000"
        self.color_error_text = self.default_color_error_text= "#000000"
        self.color_error_background = self.default_color_error_background = "#D3D3D3"
        # going to be obsolete even on Linux
        #self.statusbar_systray = False
        self.statusbar_floating = True
        self.icon_in_systray = False
        self.appindicator = False
        self.fullscreen = False
        self.fullscreen_display = 0
        self.systray_popup_offset= 10
        self.defaults_acknowledge_sticky = False
        self.defaults_acknowledge_send_notification = False
        self.defaults_acknowledge_persistent_comment = False
        self.defaults_acknowledge_all_services = False
        self.defaults_acknowledge_comment = "acknowledged"
        self.defaults_submit_check_result_comment = "check result submitted"
        self.defaults_downtime_duration_hours = "2"
        self.defaults_downtime_duration_minutes = "0"
        self.defaults_downtime_comment = "scheduled downtime"
        self.defaults_downtime_type_fixed = True
        self.defaults_downtime_type_flexible = False
        self.converted_from_single_configfile = False
        # internal flag to determine if keyring is available at all - defaults to False
        # use_system_keyring is checked and defined some lines later after config file was read
        self.keyring_available = False

        # Special FX
        # Centreon
        self.re_criticality_enabled = False
        self.re_criticality_pattern = ""
        self.re_criticality_reverse = False

        # the app is unconfigured by default and will stay so if it
        # would not find a config file
        self.unconfigured = True

        # try to use a given config file - there must be one given
        # if sys.argv is larger than 1
        if len(sys.argv) > 1:
            # MacOSX related -psn argument by launchd
            if sys.argv[1].find("-psn") != -1:
                # new configdir approach
                self.configdir = os.path.expanduser('~') + os.sep + ".nagstamon"
            else:
                # allow to give a config file
                self.configdir = sys.argv[1]

        # otherwise if there exits a configfile in current working directory it should be used
        elif os.path.exists(os.getcwd() + os.sep + "nagstamon.config"):
            self.configdir = os.getcwd() + os.sep + "nagstamon.config"
        else:
            # ~/.nagstamon/nagstamon.conf is the user conf file
            # os.path.expanduser('~') finds out the user HOME dir where
            # nagstamon expects its conf file to be
            self.configdir = os.path.expanduser('~') + os.sep + ".nagstamon"

        self.configfile = self.configdir + os.sep + "nagstamon.conf"

        # make path fit for actual os, normcase for letters and normpath for path
        self.configfile = os.path.normpath(os.path.normcase(self.configfile))

        # because the name of the configdir is also stored in the configfile
        # there may be situations where the name gets overwritten by a
        # wrong name so it will be stored here temporarily
        configdir_temp = self.configdir

        # legacy configfile treatment
        legacyconfigfile = self._LoadLegacyConfigFile()

        # default settings dicts
        self.servers = dict()
        self.actions = dict()

        if os.path.exists(self.configfile):
            # instantiate a Configparser to parse the conf file
            # SF.net bug #3304423 could be fixed with allow_no_value argument which
            # is only available since Python 2.7
            if sys.version_info[0] < 3 and sys.version_info[1] < 7:
                config = ConfigParser.ConfigParser()
            else:
                config = ConfigParser.ConfigParser(allow_no_value=True)
            config.read(self.configfile)

            # temporary dict for string-to-bool-conversion
            BOOLPOOL = {"False": False, "True": True}

            # go through all sections of the conf file
            for section in config.sections():
                # go through all items of each sections (in fact there is only on
                # section which has to be there to comply to the .INI file standard
                for i in config.items(section):
                    # create a key of every config item with its appropriate value
                    # check first if it is a bool value and convert string if it is
                    if i[1] in BOOLPOOL:
                        object.__setattr__(self, i[0], BOOLPOOL[i[1]])
                    else:
                        object.__setattr__(self, i[0], i[1])
                        
            # because the switch from Nagstamon 1.0 to 1.0.1 brings the use_system_keyring property
            # and all the thousands 1.0 installations do not know it yet it will be more comfortable
            # for most of the Windows users if it is only defined as False after it was checked
            # from config file
            if not self.__dict__.has_key("use_system_keyring"):
                if self.unconfigured == True:
                    # an unconfigured system should start with no keyring to prevent crashes
                    self.use_system_keyring = False
                else:
                    # a configured system seemed to be able to run and thus use system keyring
                    if platform.system() in ["Windows", "Darwin"]:
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

            # if configfile has been converted from legacy configfile reset it to the new value
            self.configfile = self.configdir + os.sep + "nagstamon.conf"

        # flag to be evaluated after gui is initialized and used to show a notice if a legacy config file is used
        # from command line
        self.legacyconfigfile_notice = False

        # in case it exists and it has not been used before read legacy config file once
        if str(self.converted_from_single_configfile) == "False" and not legacyconfigfile == False:
            # instantiate a Configparser to parse the conf file
            # SF.net bug #3304423 could be fixed with allow_no_value argument which
            # is only available since Python 2.7
            if sys.version_info[0] < 3 and sys.version_info[1] < 7:
                config = ConfigParser.ConfigParser()
            else:
                config = ConfigParser.ConfigParser(allow_no_value=True)
            config.read(legacyconfigfile)

            # go through all sections of the conf file
            for section in config.sections():
                if section.startswith("Server_"):
                    # create server object for every server
                    server_name = dict(config.items(section))["name"]
                    self.servers[server_name] = Server()

                    # go through all items of each sections
                    for i in config.items(section):
                            self.servers[server_name].__setattr__(i[0], i[1])

                    # deobfuscate username + password inside a try-except loop
                    # if entries have not been obfuscated yet this action should raise an error
                    # and old values (from nagstamon < 0.9.0) stay and will be converted when next
                    # time saving config
                    try:
                        self.servers[server_name].username = self.DeObfuscate(self.servers[server_name].username)
                        if self.servers[server_name].save_password == "False":
                            self.servers[server_name].password = ""
                        else:
                            self.servers[server_name].password = self.DeObfuscate(self.servers[server_name].password)
                        self.servers[server_name].autologin_key  = self.DeObfuscate(self.servers[server_name].autologin_key)
                        self.servers[server_name].proxy_username = self.DeObfuscate(self.servers[server_name].proxy_username)
                        self.servers[server_name].proxy_password = self.DeObfuscate(self.servers[server_name].proxy_password)
                    except:
                        pass

                elif section == "Nagstamon":
                    # go through all items of each sections (in fact there is only on
                    # section which has to be there to comply to the .INI file standard
                    for i in config.items(section):
                        # create a key of every config item with its appropriate value - but please no legacy config file
                        if not i[0] == "configfile":
                            object.__setattr__(self, i[0], i[1])

            # add default actions as examples
            self.actions.update(self._DefaultActions())

            # set flag for config file not being evaluated again
            self.converted_from_single_configfile = True
            # of course Nagstamon is configured then
            self.unconfigured = False

            # add config dir in place of legacy config file
            # in case there is a default install use the default config dir
            if legacyconfigfile == os.path.normpath(os.path.normcase(os.path.expanduser('~') + os.sep + ".nagstamon.conf")):
                self.configdir = os.path.normpath(os.path.normcase(os.path.expanduser('~') + os.sep + ".nagstamon"))
            else:
                self.configdir = legacyconfigfile + ".config"
            self.configfile = self.configdir + os.sep + "nagstamon.conf"

            # set flag to show legacy command line config file notice
            self.legacyconfigfile_notice = True

            # save converted configuration
            self.SaveConfig()

        # Load actions if Nagstamon is not unconfigured, otherwise load defaults
        if str(self.unconfigured) == "True":
            self.actions = self._DefaultActions()

        # do some conversion stuff needed because of config changes and code cleanup
        self._LegacyAdjustments()


    def _LoadServersMultipleConfig(self):
        """
        load servers config - special treatment because of obfuscated passwords
        """
        self.keyring_available = self.KeyringAvailable()

        servers = self.LoadMultipleConfig("servers", "server", "Server")
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
                if servers[server].save_password == "False":
                    servers[server].password = ""
                elif self.keyring_available and self.use_system_keyring:
                    # necessary to import on-the-fly due to possible Windows crashes
                    try:
                        import keyring
                    except:
                        import Nagstamon.thirdparty.keyring as keyring
                    password = keyring.get_password("Nagstamon", "@".join((servers[server].username,
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
                    try:
                        import keyring
                    except:
                        import Nagstamon.thirdparty.keyring as keyring
                    proxy_password = keyring.get_password("Nagstamon", "@".join(("proxy",
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
                if servers[server].__dict__.has_key("autologin_key"):
                    if len(servers[server].__dict__["autologin_key"]) > 0:
                        servers[server].autologin_key  = self.DeObfuscate(servers[server].autologin_key)
        except:
            import traceback
            traceback.print_exc(file=sys.stdout)

        return servers


    def _LoadLegacyConfigFile(self):
        """
        load any pre-0.9.9 config file
        """
        # default negative setting
        legacyconfigfile = False

        # try to use a given config file - there must be one given
        # if sys.argv is larger than 1
        if len(sys.argv) > 1:
            if sys.argv[1].find("-psn") != -1:
                legacyconfigfile = os.path.expanduser('~') + os.sep + ".nagstamon.conf"
            else:
                # allow to give a config file
                legacyconfigfile = sys.argv[1]
        # otherwise if there exits a configfile in current working directory it should be used
        elif os.path.exists(os.getcwd() + os.sep + "nagstamon.conf"):
            legacyconfigfile = os.getcwd() + os.sep + "nagstamon.conf"
        else:
            # ~/.nagstamon.conf is the user conf file
            # os.path.expanduser('~') finds out the user HOME dir where
            # nagstamon expects its conf file to be
            legacyconfigfile = os.path.expanduser('~') + os.sep + ".nagstamon.conf"

        # make path fit for actual os, normcase for letters and normpath for path
        legacyconfigfile = os.path.normpath(os.path.normcase(legacyconfigfile))

        if os.path.exists(legacyconfigfile) and os.path.isfile(legacyconfigfile):
            return legacyconfigfile
        else:
            return False


    def LoadMultipleConfig(self, settingsdir, setting, configobj):
        """
        load generic config into settings dict and return to central config
        """
        # defaults as empty dict in case settings dir/files could not be found
        settings = dict()

        try:
            if os.path.exists(self.configdir + os.sep + settingsdir):
                # dictionary that later gets returned back
                settings = dict()
                for f in os.listdir(self.configdir + os.sep + settingsdir):
                    if f.startswith(setting + "_") and f.endswith(".conf"):
                        if sys.version_info[0] < 3 and sys.version_info[1] < 7:
                            config = ConfigParser.ConfigParser()
                        else:
                            config = ConfigParser.ConfigParser(allow_no_value=True)
                        config.read(self.configdir + os.sep + settingsdir + os.sep + f)

                        # create object for every setting
                        name = f.split("_", 1)[1].rpartition(".")[0]
                        settings[name] = globals()[configobj]()

                        # go through all items of the server
                        for i in config.items(setting + "_" + name):
                            # create a key of every config item with its appropriate value
                            settings[name].__setattr__(i[0], i[1])
        except:
            import traceback
            traceback.print_exc(file=sys.stdout)

        return settings


    def SaveConfig(self, output=None, server=None, debug_queue=None):
        """
            save config file
            "output", "server" and debug_queue are used only for debug purpose - which one is given will be taken
        """
        try:
            # Make sure .nagstamon is created
            if not os.path.exists(self.configdir):
                os.mkdir(self.configdir)
            # save config file with ConfigParser
            config = ConfigParser.ConfigParser()
            # general section for Nagstamon
            config.add_section("Nagstamon")
            for option in self.__dict__:
                if not option in ["servers", "actions"]:
                    config.set("Nagstamon", option, self.__dict__[option])

            # because the switch from Nagstamon 1.0 to 1.0.1 brings the use_system_keyring property
            # and all the thousands 1.0 installations do not know it yet it will be more comfortable
            # for most of the Windows users if it is only defined as False after it was checked
            # from config file
            if not self.__dict__.has_key("use_system_keyring"):
                if self.unconfigured == True:
                    # an unconfigured system should start with no keyring to prevent crashes
                    self.use_system_keyring = False
                else:
                    # a configured system seemed to be able to run and thus use system keyring
                    if platform.system() in ["Windows", "Darwin"]:
                        self.use_system_keyring = True
                    else:
                        self.use_system_keyring = self.KeyringAvailable()

            # save servers dict
            self.SaveMultipleConfig("servers", "server")

            # save actions dict
            self.SaveMultipleConfig("actions", "action")

            # debug
            if str(self.debug_mode) == "True":
                if server != None:
                    server.Debug(server="", debug="Saving config to " + self.configfile)
                elif output != None:
                    output.servers.values()[0].Debug(server="", debug="Saving config to " + self.configfile)

            # open, save and close config file
            f = open(os.path.normpath(self.configfile), "w")
            config.write(f)
            f.close()
        except Exception, err:
            print err
            import traceback
            traceback.print_exc(file=sys.stdout)

            # debug
            if str(self.debug_mode) == "True":
                if server != None:
                    server.Debug(server="", debug="Saving config to " + self.configfile)
                elif output != None:
                    output.servers.values()[0].Debug(server="", debug="Saving config to " + self.configfile)
                elif debug_queue != None:
                    debug_string =  " ".join((head + ":",  str(datetime.datetime.now()), "Saving config to " + self.configfile))
                    # give debug info to debug loop for thread-save log-file writing
                    self.debug_queue.put(debug_string)


    def SaveMultipleConfig(self, settingsdir, setting):
        """
        saves conf files for settings like actions in extra directories
        "multiple" means that multiple confs for actions or servers are loaded,
        not just one like for e.g. sound file
        """

        # only import keyring lib if configured to do so - to avoid Windows crashes
        # like https://github.com/HenriWahl/Nagstamon/issues/97
        if self.use_system_keyring == True:
            self.keyring_available = self.KeyringAvailable()

        # one section for each setting
        for s in self.__dict__[settingsdir]:
            # depending on python version allow_no_value is allowed or not
            if sys.version_info[0] < 3 and sys.version_info[1] < 7:
                config = ConfigParser.ConfigParser()
            else:
                config = ConfigParser.ConfigParser(allow_no_value=True)
            config.add_section(setting + "_" + s)
            for option in self.__dict__[settingsdir][s].__dict__:
                # obfuscate certain entries in config file - special arrangement for servers
                if settingsdir == "servers":
                    #if option == "username" or option == "password" or option == "proxy_username" or option == "proxy_password" or option == "autologin_key":
                    if option in ["username", "password", "proxy_username", "proxy_password", "autologin_key"]:
                        value = self.Obfuscate(self.__dict__[settingsdir][s].__dict__[option])
                        if option == "password":
                            if self.__dict__[settingsdir][s].save_password == "False":
                                value = ""
                            elif self.keyring_available and self.use_system_keyring:
                                if self.__dict__[settingsdir][s].password != "":
                                    # necessary to import on-the-fly due to possible Windows crashes
                                    try:
                                        import keyring
                                    except:
                                        import Nagstamon.thirdparty.keyring as keyring
                                    # provoke crash if password saving does not work - this is the case
                                    # on newer Ubuntu releases
                                    try:
                                        keyring.set_password("Nagstamon", "@".join((self.__dict__[settingsdir][s].username,
                                                                                self.__dict__[settingsdir][s].monitor_url)),
                                                                                self.__dict__[settingsdir][s].password)
                                    except:
                                        import traceback
                                        traceback.print_exc(file=sys.stdout)
                                        sys.exit(1)
                                value = ""
                        if option == "proxy_password":
                            if self.keyring_available and self.use_system_keyring:
                                # necessary to import on-the-fly due to possible Windows crashes
                                try:
                                    import keyring
                                except:
                                    import Nagstamon.thirdparty.keyring as keyring
                                if self.__dict__[settingsdir][s].proxy_password != "":
                                    # provoke crash if password saving does not work - this is the case
                                    # on newer Ubuntu releases
                                    try:
                                        keyring.set_password("Nagstamon", "@".join(("proxy",\
                                                                                self.__dict__[settingsdir][s].proxy_username,
                                                                                self.__dict__[settingsdir][s].proxy_address)),
                                                                                self.__dict__[settingsdir][s].proxy_password)
                                    except:
                                        import traceback
                                        traceback.print_exc(file=sys.stdout)
                                        sys.exit(1)

                                value = ""
                        config.set(setting + "_" + s, option, value)
                    else:
                        config.set(setting + "_" + s, option, self.__dict__[settingsdir][s].__dict__[option])
                else:
                    config.set(setting + "_" + s, option, self.__dict__[settingsdir][s].__dict__[option])

            # open, save and close config_server file
            if not os.path.exists(self.configdir + os.sep + settingsdir):
                os.mkdir(self.configdir + os.sep + settingsdir)
            f = open(os.path.normpath(self.configdir + os.sep + settingsdir + os.sep + setting + "_" + s + ".conf"), "w")
            config.write(f)
            f.close()

        # clean up old deleted/renamed config files
        if os.path.exists(self.configdir + os.sep + settingsdir):
            for f in os.listdir(self.configdir + os.sep + settingsdir):
                if not f.split(setting + "_")[1].split(".conf")[0] in self.__dict__[settingsdir]:
                    os.unlink(self.configdir + os.sep + settingsdir + os.sep + f)


    def Convert_Conf_to_Multiple_Servers(self):
        """
            if there are settings found which come from older nagstamon version convert them -
            now with multiple servers support these servers have their own settings

            DEPRECATED I think, after 2,5 years have passed there should be no version less than 0.8.0 in the wild...
        """

        # check if old settings exist
        if self.__dict__.has_key("nagios_url") and \
            self.__dict__.has_key("nagios_cgi_url") and \
            self.__dict__.has_key("username") and \
            self.__dict__.has_key("password") and \
            self.__dict__.has_key("use_proxy_yes") and \
            self.__dict__.has_key("use_proxy_no"):
            # create Server and fill it with old settings
            server_name = "Default"
            self.servers[server_name] = Server()
            self.servers[server_name].name = server_name
            self.servers[server_name].monitor_url = self.nagios_url
            self.servers[server_name].monitor_cgi_url = self.nagios_cgi_url
            self.servers[server_name].username = self.username
            self.servers[server_name].password = self.password
            # convert VERY old config files
            try:
                self.servers[server_name].use_proxy = self.use_proxy_yes
            except:
                self.servers[server_name].use_proxy = False
            try:
                self.servers[server_name].use_proxy_from_os = self.use_proxy_from_os_yes
            except:
                self.servers[server_name].use_proxy_from_os = False
            # delete old settings from config
            self.__dict__.pop("nagios_url")
            self.__dict__.pop("nagios_cgi_url")
            self.__dict__.pop("username")
            self.__dict__.pop("password")
            self.__dict__.pop("use_proxy_yes")
            self.__dict__.pop("use_proxy_no")


    def KeyringAvailable(self):
        """
            determine if keyring module and an implementation is available for secure password storage
        """
        try:
            # Linux systems should use keyring only if it comes with the distro, otherwise chances are small
            # that keyring works at all
            if not platform.system() in ["Windows", "Darwin"]:
                # keyring and secretstorage have to be importable
                import keyring, secretstorage
                if ("SecretService") in dir(keyring.backends) and not (keyring.get_keyring() is None):
                    return True
            else:
                # safety first - if not yet available disable it
                if not self.__dict__.has_key("use_system_keyring"):
                    self.use_system_keyring = False
                # only import keyring lib if configured to do so
                # necessary to avoid Windows crashes like https://github.com/HenriWahl/Nagstamon/issues/97
                if self.use_system_keyring == True:
                    # hint for packaging: nagstamon.spec always have to match module path
                    # keyring has to be bound to object to be used later
                    import Nagstamon.thirdparty.keyring as keyring
                    return  not (keyring.get_keyring() is None)
                else:
                    return False
        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            return False


    def Convert_Conf_to_Custom_Actions(self):
        """
        any nagstamon minor to 0.9.9 will have extra ssh/rdp/vnc settings
        which will be converted to custom actions here
        """

        # check if old settings exist
        if self.__dict__.has_key("app_ssh_bin") and \
            self.__dict__.has_key("app_ssh_options") and \
            self.__dict__.has_key("app_rdp_bin") and \
            self.__dict__.has_key("app_rdp_options") and \
            self.__dict__.has_key("app_vnc_bin") and \
            self.__dict__.has_key("app_vnc_options"):
            # create actions and fill them with old settings
            self.actions["SSH"] = Action(name="SSH", type="command", description="Converted from pre 0.9.9 Nagstamon.",
                                         string=self.app_ssh_bin + " " + self.app_ssh_options + " $ADDRESS$")

            self.actions["RDP"] = Action(name="RDP", type="command", description="Converted from pre 0.9.9 Nagstamon.",
                                         string=self.app_rdp_bin + " " + self.app_rdp_options + " $ADDRESS$")

            self.actions["VNC"] = Action(name="VNC", type="command", description="Converted from pre 0.9.9 Nagstamon.",
                                         string=self.app_vnc_bin + " " + self.app_vnc_options + " $ADDRESS$")

            # delete old settings from config
            self.__dict__.pop("app_ssh_bin")
            self.__dict__.pop("app_ssh_options")
            self.__dict__.pop("app_rdp_bin")
            self.__dict__.pop("app_rdp_options")
            self.__dict__.pop("app_vnc_bin")
            self.__dict__.pop("app_vnc_options")


    def Obfuscate(self, string, count=5):
        """
            Obfuscate a given string to store passwords etc.
        """
        for i in range(count):
            string = list(base64.b64encode(string))
            string.reverse()
            string = "".join(string)
            string = zlib.compress(string)
        string = base64.b64encode(string)
        return string


    def DeObfuscate(self, string, count=5):
        string = base64.b64decode(string)
        for i in range(count):
            string = zlib.decompress(string)
            string = list(string)
            string.reverse()
            string = "".join(string)
            string = base64.b64decode(string)
        return string


    def _DefaultActions(self):
        """
        create some default actions like SSH and so on
        """
        if platform.system() == "Windows":
            defaultactions = { "RDP": Action(name="RDP", description="Connect via RDP.",
                                    type="command", string="C:\windows\system32\mstsc.exe $ADDRESS$"),
                               "VNC": Action(name="VNC", description="Connect via VNC.",
                                    type="command", string="C:\Program Files\TightVNC\vncviewer.exe $ADDRESS$"),
                               "Telnet": Action(name="Telnet", description="Connect via Telnet.",
                                    type="command", string="C:\Windows\System32\Telnet.exe root@$ADDRESS$"),
                               "SSH": Action(name="SSH", description="Connect via SSH.",
                                    type="command", string="C:\Program Files\PuTTY\putty.exe -l root $ADDRESS$")
                               }
        elif platform.system() == "Darwin":
            defaultactions = { "RDP": Action(name="RDP", description="Connect via RDP.",
                                    type="command", string="open rdp://$ADDRESS$"),
                               "VNC": Action(name="VNC", description="Connect via VNC.",
                                    type="command", string="open vnc://$ADDRESS$"),
                               "SSH": Action(name="SSH", description="Connect via SSH.",
                                    type="command", string="open ssh://root@$ADDRESS$"),
                               "Telnet": Action(name="Telnet", description="Connect via Telnet.",
                                    type="command", string="open telnet://root@$ADDRESS$")
                               }
        else:
            # the Linux settings
            defaultactions = { "RDP": Action(name="RDP", description="Connect via RDP.",
                                    type="command", string="/usr/bin/rdesktop -g 1024x768 $ADDRESS$"),
                               "VNC": Action(name="VNC", description="Connect via VNC.",
                                    type="command", string="/usr/bin/vncviewer $ADDRESS$"),
                               "SSH": Action(name="SSH", description="Connect via SSH.",
                                    type="command", string="/usr/bin/gnome-terminal -x ssh root@$ADDRESS$"),
                               "Telnet": Action(name="Telnet", description="Connect via Telnet.",
                                    type="command", string="/usr/bin/gnome-terminal -x telnet root@$ADDRESS$"),
                               "Update-Linux": Action(name="Update-Linux", description="Run remote update script.",
                                    type="command", string="/usr/bin/terminator -x ssh root@$HOST$ update.sh",
                                    enabled=False)
                               }
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
                                                     string="$MONITOR$/index.py?start_url=%2Fmonitor%2Fcheck_mk%2Fwato.py%3Fmode%3Dedithost%26host%3D$HOST$")
        defaultactions["Email"] = Action(name="Email", enabled=False, description="Send email to someone.", type="browser",
                                                    string="mailto:servicedesk@my.org?subject=Monitor alert: $HOST$ - $SERVICE$ - $STATUS-INFO$&body=Please help!.%0d%0aBest regards from Nagstamon")

        return defaultactions


    def _LegacyAdjustments(self):
        # mere cosmetics but might be more clear for future additions - changing any "nagios"-setting to "monitor"
        for s in self.servers.values():
            if s.__dict__.has_key("nagios_url"):
                s.monitor_url = s.nagios_url
            if s.__dict__.has_key("nagios_cgi_url"):
                s.monitor_cgi_url = s.nagios_cgi_url

            # to reduce complexity in Centreon there is also only one URL necessary
            if s.type == "Centreon":
                s.monitor_url = s.monitor_cgi_url

        # switch to update interval in seconds not minutes
        if self.__dict__.has_key("update_interval"):
            self.update_interval_seconds = int(self.update_interval) * 60
            self.__dict__.pop("update_interval")

        # remove support for GNOME2-trayicon-egg-stuff
        if self.__dict__.has_key("statusbar_systray"):
            if str(self.statusbar_systray) == "True":
                self.icon_in_systray = "True"
            self.__dict__.pop("statusbar_systray")


    def GetNumberOfEnabledMonitors(self):
        """
        returns the number of enabled monitors - in case all are disabled there is no need to display the popwin
        """
        # to be returned
        number = 0
        for server in self.servers.values():
            if str(server.enabled) == "True":
                number += 1
        return number


class Server(object):
    """
    one Server realized as object for config info
    """
    def __init__(self):
        self.enabled = True
        self.type = "Nagios"
        self.name = ""
        self.monitor_url = ""
        self.monitor_cgi_url = ""
        self.username = ""
        self.password = ""
        self.save_password = True
        self.use_proxy = False
        self.use_proxy_from_os = False
        self.proxy_address = ""
        self.proxy_username = ""
        self.proxy_password = ""

        # special FX
        # Centreon autologin
        self.use_autologin = False
        self.autologin_key = ""

        # Icinga "host_display_name" instead of "host"
        self.use_display_name_host = False
        self.use_display_name_service = False


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

        # special FX
        # Centreon criticality and autologin
        self.re_criticality_enabled = False
        self.re_criticality_pattern = ""
        self.re_criticality_reverse = False

        # add and/or all keywords to object
        for k in kwds: self.__dict__[k] = kwds[k]
