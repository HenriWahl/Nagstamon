# encoding: utf-8

from Nagstamon.Server.Generic import GenericServer


class NagiosServer(GenericServer):
    """
        object of Nagios server - when nagstamon will be able to poll various servers this
        will be useful
        As Nagios is the default server type all its methods are in GenericServer
    """

    TYPE = 'Nagios'

    # autologin is used only by Centreon
    DISABLED_CONTROLS = ["input_checkbutton_use_autologin", "label_autologin_key", "input_entry_autologin_key"]

