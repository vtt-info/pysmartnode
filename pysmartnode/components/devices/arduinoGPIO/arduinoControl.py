# Author: Kevin Köck
# Copyright Kevin Köck 2019 Released under the MIT license
# Created on 2019-03-31 

__updated__ = "2019-04-08"
__version__ = "0.1"

"""
ArduinoControl Instance
{
    package: .arduinoGPIO.arduinoControl
    component: ArduinoControl
    constructor_args: {
        pin: 2                              # pin number or object
        # expected_devices: ["ROM","ROM"]   # list of ROMs or amount of devices, optional 
    }
}

ArduinoControl Pin instance
{
    package: .arduinoGPIO.arduino
    component: Pin
    constructor_args: {
        arduinoControl: "arduinoControlName"   # ArduinoControl instance
        rom: "ArduinoROM"        # Arduino device ROM 
        pin: 4                   # Pin number
        mode: 1                  # Arduino pin mode, ArduinoInteger
        value: 0                 # Starting value of the pin 
    }
}

ArduinoControl ADC instance
{
    package: .arduinoGPIO.arduino
    component: ADC
    constructor_args: {
        arduinoControl: "arduinoControlName"   # ArduinoControl instance
        rom: "ArduinoROM"        # Arduino device ROM 
        pin: 0                   # Pin number
        # vcc: 5                 # Arduino VCC voltage 
    }
}
"""

from pysmartnode.libraries.arduinoGPIO.arduinoGPIO.arduinoControl import ArduinoControl as _ArduinoControl
from pysmartnode.components.machine.pin import Pin as PyPin
from pysmartnode import logging

log = logging.getLogger("Arduino")


class ArduinoControl(_ArduinoControl):
    def __init__(self, pin: any, expected_devices=None):
        """
        Class to remotely control an Arduino
        :param pin: Pin number/name/object of the onewire connection
        :param expected_devices: used to warn if devices go missing (filters non-arduino devices)
        """
        pin = PyPin(pin)
        if type(expected_devices) == list:
            for i in range(expected_devices):
                if type(expected_devices[i]) == str:
                    expected_devices[i] = self.str2rom(expected_devices[i])
        super().__init__(pin, expected_devices)

    def _error(self, message):
        log.error(message)


def Pin(arduinoControl: ArduinoControl, rom: bytearray, pin: int, *args, **kwargs):
    if type(rom) == str:
        rom = arduinoControl.str2rom(rom)
    return arduinoControl.Pin(rom, pin, *args, **kwargs)


def ADC(arduinoControl: ArduinoControl, rom: bytearray, pin: int, vcc: int = 5):
    if type(rom) == str:
        rom = arduinoControl.str2rom(rom)
    return arduinoControl.ADC(rom, pin, vcc)
