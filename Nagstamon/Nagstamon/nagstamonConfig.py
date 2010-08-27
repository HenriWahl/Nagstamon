# encoding: utf-8

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
        """
        # supposed to be sensible defaults
        self.update_interval = 1
        self.short_display = False
        self.long_display = True
        self.filter_all_down_hosts = False
        self.filter_all_unreachable_hosts = False
        self.filter_all_unknown_services = False
        self.filter_all_warning_services = False
        self.filter_all_critical_services = False
        self.filter_acknowledged_hosts_services = False
        self.filter_hosts_services_disabled_notifications = False
        self.filter_hosts_services_disabled_checks = False
        self.filter_hosts_services_maintenance = False
        self.filter_services_on_down_hosts = False
        self.filter_services_on_hosts_in_maintenance = False
        self.filter_services_on_unreachable_hosts = False
        self.filter_services_in_soft_state = False
        self.position_x = 0
        self.position_y = 0
        self.popup_details_hover = True
        self.popup_details_clicking = False
        self.connect_by_dns_yes = True
        self.connect_by_dns_no = False
        self.debug_mode = False
        self.check_for_new_version = True
        self.notification = True
        self.notification_flashing = True
        # because of nonexistent windows systray popup support I'll let it be now
        #self.notification_popup = False
        self.notification_sound = True
        self.notification_default_sound = True
        self.notification_custom_sound = False      
        self.notification_custom_sound_warning = None
        self.notification_custom_sound_critical = None
        self.notification_custom_sound_down = None
        self.notify_if_warning = True
        self.notify_if_critical = True
        self.notify_if_unknown = True
        self.notify_if_unreachable = True
        self.notify_if_down = True
        self.re_host_enabled = False
        self.re_host_pattern = ""
        self.re_host_reverse = False
        self.re_service_enabled = False
        self.re_service_pattern = ""
        self.re_service_reverse = False

        # those are example Windows settings, almost certainly a
        # user will have to fix them for his computer
        if platform.system() == "Windows":
            self.app_ssh_bin = "C:\Program Files\PuTTY\putty.exe"
            self.app_rdp_bin = "C:\windows\system32\mstsc.exe"
            self.app_vnc_bin = "C:\Program Files\TightVNC\\vncviewer.exe"
            self.app_ssh_options = "-l root"
            self.app_rdp_options = "/v:"
            self.app_vnc_options = ""
            self.statusbar_systray = False
            self.statusbar_floating = True
            self.icon_in_systray = False
        else:
            # the Linux settings
            self.app_ssh_bin = "/usr/bin/gnome-terminal -x ssh"
            self.app_rdp_bin = "/usr/bin/rdesktop"
            self.app_vnc_bin = "/usr/bin/vncviewer"
            self.app_ssh_options = "-l root"
            self.app_rdp_options = "-g 1024x768"
            self.app_vnc_options = ""
            # if running in GNOME defaulting to systray statusbar, otherwise
            # to floating statusbar
            if os.environ.has_key("DESKTOP_SESSION"):
                if os.environ["DESKTOP_SESSION"] == "gnome":
                    self.statusbar_systray = True
                    self.statusbar_floating = False
                    self.icon_in_systray = False
                else:
                    self.statusbar_systray = False
                    self.statusbar_floating = True
                    self.icon_in_systray = False
            else:
                # in case nagstamon is run from console without any desktop session
                # choose floating statusbar as default
                self.statusbar_systray = False
                self.statusbar_floating = True
                self.icon_in_systray = False
        
        # the app is unconfigured by default and will stay so if it
        # would not find a config file
        self.unconfigured = True

        # try to use a given config file - there must be one given
        # if sys.argv is larger than 1
        if len(sys.argv) > 1:
            # allow to give a config file
            self.configfile = sys.argv[1]
        # otherwise if there exits a configfile in current working directory it should be used
        elif os.path.exists(os.getcwd() + "/nagstamon.conf"):
            self.configfile = os.getcwd() + "/nagstamon.conf"
        else:
            # ~/.nagstamon.conf is the user conf file
            # os.path.expanduser('~') finds out the user HOME dir where 
            # nagstamon expects its conf file to be
            self.configfile = os.path.expanduser('~') + "/.nagstamon.conf"

        # make path fit for actual os, normcase for letters and normpath for path
        self.configfile = os.path.normpath(os.path.normcase(self.configfile))

        # because the name of the configfile is also stored in the configfile
        # there may be situations where the name gets overwritten by a
        # wrong name so it will be stored here temporarily
        configfile_temp = self.configfile
    
        # dictionary containing the config data for different servers
        self.servers = dict()
            
        if os.path.exists(self.configfile):
            # instantiate a Configparser to parse the conf file
            config = ConfigParser.ConfigParser()
            config.read(self.configfile)
            
            # go through all sections of the conf file
            for section in config.sections():
                if section.startswith("Server_"):
                    # create server object for every server
                    server_name = dict(config.items(section))["name"]
                    self.servers[server_name] = Server()                  
                    
                    # go through all items of each sections
                    for i in config.items(section):
                        # create a key of every config item with its appropriate value
                        self.servers[server_name].__setattr__(i[0], i[1])
                        
                    # deobfuscate username + password inside a try-except loop
                    # if entries have not been obfuscated yet this action should raise an error
                    # and old values (from nagstamon < 0.9.0) stay and will be converted when next
                    # time saving config
                    try:
                        self.servers[server_name].username = self.DeObfuscate(self.servers[server_name].username)
                        self.servers[server_name].password = self.DeObfuscate(self.servers[server_name].password)
                        self.servers[server_name].proxy_username = self.DeObfuscate(self.servers[server_name].proxy_username)
                        self.servers[server_name].proxy_password = self.DeObfuscate(self.servers[server_name].proxy_password)
                    except:
                        pass
                                       
                elif section == "Nagstamon":
                    # go through all items of each sections (in fact there is only on
                    # section which has to be there to comply to the .INI file standard
                    for i in config.items(section):
                        # create a key of every config item with its appropriate value
                        object.__setattr__(self, i[0], i[1])

            # seems like there is a config file so the app is not unconfigured anymore
            self.unconfigured = False
            
            # reset self.configfile to temporarily saved value in case it differs from
            # the one read from configfile and so it would fail to save next time
            self.configfile = configfile_temp
            

    #def __del__(self):
    #    """
    #    hopefully a __del__() method may make this object better collectable for gc
    #    """
    #    del(self)
            

    def SaveConfig(self):
        """
            save config file
        """
        try:
            # save config file with ConfigParser
            config = ConfigParser.ConfigParser()
            # general section for Nagstamon
            config.add_section("Nagstamon")
            for option in self.__dict__:
                if not option == "servers":
                    config.set("Nagstamon", option, self.__dict__[option])
            # one section for each configured server
            for server in self.__dict__["servers"]:
                config.add_section("Server_" + server)
                for option in self.__dict__["servers"][server].__dict__:
                    # obfuscate certain entries in config file
                    if option == "username" or option == "password" or option == "proxy_username" or option == "proxy_password":
                        config.set("Server_" + server, option, self.Obfuscate(self.__dict__["servers"][server].__dict__[option]))
                    else:
                        config.set("Server_" + server, option, self.__dict__["servers"][server].__dict__[option])
            # open, save and close config file
            f = open(os.path.normpath(self.configfile), "w")
            config.write(f)
            f.close()
            
        except:
            pass


    def Convert_Conf_to_Multiple_Servers(self):
        """
            if there are settings found which come from older nagstamon version convert them -
            now with multiple servers support these servers have their own settings
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
            self.servers[server_name].nagios_url = self.nagios_url
            self.servers[server_name].nagios_cgi_url = self.nagios_cgi_url
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
            # save config
            self.SaveConfig()
        
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
    

class Server(object):
    """
    one Server realized as object for config info
    """
    def __init__(self):
        self.enabled = True
        self.type = "Nagios"
        self.name = ""
        self.nagios_url = ""
        self.nagios_cgi_url = ""
        self.username = ""
        self.password = ""
        self.use_proxy = False
        self.use_proxy_from_os = False
        self.proxy_address = ""
        self.proxy_username = ""
        self.proxy_password = ""
        
    
    #def __del__(self):
    #    """
    #    hopefully a __del__() method may make this object better collectable for gc
    #    """
    #    del(self)

