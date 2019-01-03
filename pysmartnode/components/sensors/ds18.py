'''
Created on 2018-06-25

@author: Kevin Köck
'''

"""
example config:
{
    package: .sensors.ds18
    component: DS18
    constructor_args: {
        pin: 5                    # pin number or label (on NodeMCU)
        precision_temp: 2         #precision of the temperature value published
        precision_humid: 1        #precision of the humid value published
        offset_temp: 0            #offset for temperature to compensate bad sensor reading offsets
        offset_humid: 0           #...             
        #interval: 600            #optional, defaults to 600
        #mqtt_topic: sometopic  #optional, defaults to home/<controller-id>/DS18, multiple sensor to /DS18_<count>
    }
}
"""

__updated__ = "2018-08-31"
__version__ = "0.3"

from pysmartnode import config
from pysmartnode import logging
import uasyncio as asyncio
import gc
from pysmartnode.components.machine.pin import Pin
from sys import platform

####################
# import your library here
if platform == "esp8266":
    import ds18x20
    from onewire import OneWire
elif platform == "esp32_LoBo":
    from machine import OneWire

# choose a component name that will be used for logging (not in leightweight_log) and
# a default mqtt topic that can be changed by received or local component configuration
_component_name = "DS18"
####################

_log = logging.getLogger(_component_name)
_mqtt = config.getMQTT()
gc.collect()


class DS18(ds18x20.DS18x20 if platform != "esp32_LoBo" else OneWire.ds18x20):
    def __init__(self, pin, precision_temp=2, precision_humid=1,  # extend or shrink according to your sensor
                 offset_temp=0, offset_humid=0,  # also here
                 interval=None, mqtt_topic=None):
        interval = interval or config.INTERVAL_SEND_SENSOR
        self.topic = mqtt_topic or _mqtt.getDeviceTopic(_component_name)

        ##############################
        # adapt to your sensor by extending/removing unneeded values like in the constructor arguments
        self._prec_temp = int(precision_temp)
        self._prec_humid = int(precision_humid)
        ###
        self._offs_temp = float(offset_temp)
        self._offs_humid = float(offset_humid)
        ##############################
        # create sensor object
        super().__init__(OneWire(Pin(pin)) if platform != "esp32_LoBo" else OneWire(pin, 0))
        ##############################
        # choose a background loop that periodically reads the values and publishes it
        # (function is created below)
        background_loop = self.temperature
        ##############################
        gc.collect()
        asyncio.get_event_loop().create_task(self._loop(background_loop, interval))

    async def _loop(self, gen, interval):
        while True:
            await gen()
            await asyncio.sleep(interval)

    async def _read(self, prec, offs, publish=True):
        roms = self.scan()
        if len(roms) == 0:
            _log.error("No DS18 found")
            return None
        # until here changed for lobo, but not esp32 mainline
        self.convert_temp()
        await asyncio.sleep_ms(750)
        values = []
        for rom in roms:
            values.append(self.read_temp(rom))
            if values[-1] is not None:
                try:
                    values[-1] = round(values[-1], prec)
                    values[-1] += offs
                except Exception as e:
                    _log.error("Error rounding value {!s} of rom {!s}".format(values[-1], rom))
                    values[-1] = None
            else:
                _log.warn("Sensor {!s}, rom {!s} got no value".format(_component_name, rom))
        if publish:
            if len(values) == 1:
                await _mqtt.publish(self.topic, ("{0:." + str(prec) + "f}").format(values[0]))
            else:
                for i in range(0, len(values)):
                    if values[i] is not None:
                        await _mqtt.publish("{!s}_{!s}".format(self.topic, i),
                                            ("{0:." + str(prec) + "f}").format(values[i]))
        return values

    ##############################
    # remove or add functions below depending on the values of your sensor

    async def temperature(self, sensor_number=0, publish=True):
        """sensor_number: number of sensor in roms, None for all values"""
        values = await self._read(self._prec_temp, self._offs_temp, publish)
        return values if sensor_number is None else values[sensor_number]

    ##############################
