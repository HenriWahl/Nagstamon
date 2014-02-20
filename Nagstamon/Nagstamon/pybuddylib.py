#!/usr/bin/env python
#
# pybuddylib.py: simple library to control iBuddy USB device
#    by ewall <e@ewall.org>, Sept 2010
#
# borrows code from http://code.google.com/p/pybuddy
#    by Jose.Carlos.Luna@gmail.com and luis.peralta@gmail.com
# who got most of the code from http://cuntography.com/blog/?p=17
# which is based on http://scott.weston.id.au/software/pymissile/
#
# TODO: - Why does libusb require sudo/root on Linux?
#             - Why does libusb-win32 error on Windoze?
#

import logging
from time import sleep
from sys import exit

try:
    import usb
except Exception, err:
    pass

# ## Global Configuration
DEBUG = False

# ## Prepare Logging
log = logging.getLogger("pybuddy")
log.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
if DEBUG:
    console_handler.setLevel(logging.DEBUG)
else:
    console_handler.setLevel(logging.ERROR)
log.addHandler(console_handler)

# ## General USB Device Class
class UsbDevice:
    def __init__(self, vendor_id, product_id, skip):
        busses = usb.busses()
        self.handle = None
        count = 0
        for bus in busses:
            devices = bus.devices
            for dev in devices:

                if dev.idVendor == vendor_id and dev.idProduct == product_id:
                    if count == skip:
                        log.info("USB device found (vend: %s, prod: %s)." % (dev.idVendor, dev.idProduct))
                        self.dev = dev
                        self.conf = self.dev.configurations[0]
                        self.intf = self.conf.interfaces[0][0]
                        self.endpoints = []
                        for endpoint in self.intf.endpoints:
                            self.endpoints.append(endpoint)
                            log.info("USB endpoint found.")
                        return
                    else:
                        count = count + 1
        raise NoBuddyException()

    def open(self):
        # TODO: should the HID driver detachment be optional?
        self.handle = self.dev.open()

        # we need to detach HID interface
        try:
                self.handle.detachKernelDriver(0)
                self.handle.detachKernelDriver(1)
        except:
                pass

        self.handle.setConfiguration(self.conf)
        self.handle.claimInterface(self.intf)
        self.handle.setAltInterface(self.intf)

# ## iBuddy Device Class
class iBuddyDevice:
    USB_VENDOR = 0x1130
    USB_PRODUCT = int(0x0002)
    BATTERY = 0
    SETUP = (0x22, 0x09, 0x00, 0x02, 0x01, 0x00, 0x00, 0x00)
    MESS = (0x55, 0x53, 0x42, 0x43, 0x00, 0x40, 0x02)

    WAITTIME = 0.1

    LEFT = 0
    RIGHT = 1
    UP = 0
    DOWN = 1
    OFF = 0
    ON = 1

    BLUE = (0, 0, 1)
    GREEN = (0, 1, 0)
    LTBLUE = (0, 1, 1)
    PURPLE = (1, 0, 1)
    RED = (1, 0, 0)
    WHITE = (1, 1, 1)
    YELLOW = (1, 1, 0)

    CLEAR = 0xFF
    command = CLEAR

    # the following items deal with setup and control

    def __init__(self):
        self.dev = UsbDevice(self.USB_VENDOR, self.USB_PRODUCT, self.BATTERY)
        self.dev.open()
        self.dev.handle.reset()
        self.resetCmd()
        self.doCmd()

    def __send(self, inp):
        """ send your command to the device """
        try:
            self.dev.handle.controlMsg(0x21, 0x09, self.SETUP, 0x02, 0x01)
            self.dev.handle.controlMsg(0x21, 0x09, self.MESS + (inp,), 0x02, 0x01)
        except usb.USBError:
                if DEBUG:
                    self.__init__()
                    # raise
                else:
                    self.__init__()

    def doCmd(self, seconds=WAITTIME):
        """ send the command specified by the current command """
        self.__send(self.command)
        sleep(seconds)

    # the following items operate on the command to be sent next

    def resetCmd(self):
        """ reset command to default (must pump to take effect) """
        self.command = self.CLEAR

    def setReverseBitValue(self, num, value):
        """ commands are sent as disabled bits """
        if (value == 1):
            temp = 0xFF - (1 << num)
            self.command = self.command & temp
        elif (value == 0):
            temp = 1 << num
            self.command = self.command | temp

    def getReverseBitValue(self, num):
        """ what was that bit set to again? """
        temp = self.command
        temp = temp >> num
        res = not(temp & 1)
        return res

    def setHeadColors(self, red, green, blue):
        """ colors as (red, green, blue) can be on (1) or off (0) """
        self.setReverseBitValue(4, red)
        self.setReverseBitValue(5, green)
        self.setReverseBitValue(6, blue)
        self.setReverseBitValue(2, 1)

    def getHeadColors (self):
        """ returns color status as tuple representing (red, green, blue) as on (1) or off (0) """
        return self.getReverseBitValue(4), self.getReverseBitValue(5), self.getReverseBitValue(6)

    def setHeart(self, status):
        """ heart-light can be on (1) or off (0) """
        self.setReverseBitValue(7, status)

    def getHeart(self):
        """ returns heart-light status of on (1) or off (0) """
        return self.getReverseBitValue(7)

    def setWing(self, direction):
        """ move the wings iBuddyDevice.UP (0) or iBuddyDevice.DOWN (1) """
        if (direction == self.UP):
            self.setReverseBitValue(3, 1)
            self.setReverseBitValue(2, 0)
        elif(direction == self.DOWN):
            self.setReverseBitValue(3, 0)
            self.setReverseBitValue(2, 1)

    def getWing(self):
        """ returns wing status of iBuddyDevice.UP (0) or iBuddyDevice.DOWN (1) """
        return self.getReverseBitValue(2)

    def setSwivel(self, direction):
        """ swivel the body iBuddyDevice.LEFT (0) or iBuddyDevice.RIGHT (1) """
        if (direction == self.RIGHT):
            self.setReverseBitValue(1, 1)
            self.setReverseBitValue(0, 0)
        elif(direction == self.LEFT):
            self.setReverseBitValue(1, 0)
            self.setReverseBitValue(0, 1)

    def getSwivel(self):
        """ returns current swivel direction as iBuddyDevice.LEFT (0) or iBuddyDevice.RIGHT (1) """
        return self.getReverseBitValue(1)

    # the following items are macros for specific behaviors

    def doReset(self, seconds=WAITTIME):
        """ reset to default positions/off, run command immediately """
        self.resetCmd()
        self.doCmd(seconds)

    def doFlap(self, times=3, seconds=0.2):
        """ flap wings X times with Y seconds pause in between, run command immediately """
        for i in range(times):
            self.setWing(self.UP)
            self.doCmd(seconds)
            self.setWing(self.DOWN)
            self.doCmd(seconds)

    def doWiggle(self, times=3, seconds=0.2):
        """ wiggle back and forth X times with Y seconds pauses, run command immediately """
        for i in range(times):
            self.setSwivel(self.LEFT)
            self.doCmd(seconds)
            self.setSwivel(self.RIGHT)
            self.doCmd(seconds)

    def doHeartbeat(self, times=3, seconds=0.3):
        """ blink heart X times with Y seconds' pause in betwee, run command immediately """
        for i in range(times):
            self.setHeart(self.ON)
            self.doCmd(seconds)
            self.setHeart(self.OFF)
            self.doCmd(seconds)

    def doColorRGB(self, r, g, b, seconds=WAITTIME):
        """ set head color by red/green/blue values 0 or 1, run command immediately """
        self.setHeadColors(r, g, b)
        self.doCmd(seconds)

    def doColorName(self, rgb, seconds=WAITTIME):
        """ set head color with color name tuples, run command immediately """
        self.setHeadColors(*rgb)
        self.doCmd(seconds)

# # Custom Exceptions
class NoBuddyException():
    """ indicates errors communicating with iBuddy USB device """
    # def __init__(self, *args):
    #    Exception._ _init_ _(self, *args)
    #    self.wrapped_exc = sys.exc_info()
    pass

# ## Main Program
if __name__ == '__main__':

    # find iBuddy device
    log.info("Starting search...")
    try:
            buddy = iBuddyDevice()
    except NoBuddyException, e:
            log.exception("No iBuddy device found!")
            exit(1)

    # demo command macros
    buddy.doColorName(iBuddyDevice.PURPLE, 0.5)
    buddy.doColorName(iBuddyDevice.BLUE, 0.5)
    buddy.doColorName(iBuddyDevice.LTBLUE, 0.5)
    buddy.doColorName(iBuddyDevice.YELLOW, 0.5)
    buddy.doColorName(iBuddyDevice.GREEN, 0.5)
    buddy.doColorName(iBuddyDevice.RED, 0.5)
    buddy.doColorName(iBuddyDevice.WHITE, 0.5)
    buddy.doFlap()
    sleep(1)
    buddy.doWiggle()
    sleep(1)
    buddy.doHeartbeat()
    buddy.doHeartbeat()
    buddy.doHeartbeat()
    sleep(1)
    buddy.doReset()
