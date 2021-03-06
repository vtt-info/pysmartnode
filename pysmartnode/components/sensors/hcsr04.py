# Author: Kevin Köck
# Copyright Kevin Köck 2019 Released under the MIT license
# Created on 2019-03-31

__updated__ = "2019-04-09"
__version__ = "0.1"

"""
Datasheet: https://www.mpja.com/download/hc-sr04_ultrasonic_module_user_guidejohn.pdf

Warning: My sensor only read distances reliable with flat surfaces within 80cm. 
Above that the results were fluctuating heavily.

example config:
{
    package: .sensors.hcsr04
    component: HCSR04
    constructor_args: {
        pin_trigger: D5
        pin_echo: D6
        # timeout: 30000        # optional, defaults to 30000 which is around sensor maximum distance
        # temp_sensor: "ds18"   # optional, name of temperature sensor if temperature compensated measurement is needed
        # precision: 2          # precision of the distance value published
        # offset: 0             # offset for distance value to compensate bad sensor reading offsets
        # interval: 600         # optional, defaults to 600. can be changed anytime
        # mqtt_topic: null      # optional, distance gets published to this topic
        # mqtt_topic_interval: null     # optional, topic need to have /set at the end. Interval can be changed here
    }
}
"""

from pysmartnode.components.machine.pin import Pin
from pysmartnode import config
from pysmartnode import logging
import uasyncio as asyncio
import machine
import time
import gc

_component_name = "hcsr04"

_log = logging.getLogger(_component_name)
_mqtt = config.getMQTT()
gc.collect()


class HCSR04:
    def __init__(self, pin_trigger, pin_echo, timeout=30000, temp_sensor=None,
                 precision=2, offset=0,
                 interval=None, mqtt_topic=None,
                 mqtt_topic_interval=None):
        """
        HC-SR04 ultrasonic sensor.
        Be sure to connect it to 5V but use a voltage divider to connect the Echo pin to an ESP.
        :param pin_trigger: pin number/object of trigger pin
        :param pin_echo: pin number/object of echo pin
        :param timeout: reading timeout, corresponds to sensor limit range of 4m
        :param temp_sensor: temperature sensor object
        :param precision: int, precision of distance value published and returned
        :param offset: float, distance value offset, shouldn't be needed
        :param interval: float, interval in which the distance value gets measured and published
        :param mqtt_topic: distance mqtt topic
        :param mqtt_topic_interval: interval mqtt topic for changing the reading interval
        """
        self._tr = Pin(pin_trigger, mode=machine.Pin.OUT)
        self._tr.value(0)
        self._ec = Pin(pin_echo, mode=machine.Pin.IN)
        self._to = timeout
        self._temp = temp_sensor
        self._pr = int(precision)
        self._off = float(offset)
        self._topic = mqtt_topic or _mqtt.getDeviceTopic("hcsr04")
        self._topic_int = mqtt_topic_interval or _mqtt.getDeviceTopic("hcsr04/interval", is_request=True)
        self.interval = interval or config.INTERVAL_SEND_SENSOR  # can be changed anytime
        asyncio.get_event_loop().create_task(self._loop(self.distance))
        _mqtt.scheduleSubscribe(self._topic_int, self._setInterval, check_retained_state_topic=True)

    async def _loop(self, gen):
        await asyncio.sleep(1)
        while True:
            await gen()
            t = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t) < self.interval:
                # this way interval can be changed and sensor reacts within 1s
                await asyncio.sleep(1)

    async def _setInterval(self, topic, message, retained):
        """
        Method called by changing interval through mqtt message
        """
        try:
            message = float(message)
        except Exception as e:
            await _log.asyncLog("error", "Can't convert interval {!s} to float: {!s}".format(message, e))
            return
        self.interval = message
        return True  # will publish the new interval

    def _pulse(self) -> int:
        """
        Send a pulse and wait for the echo pin using machine.time_pulse_us() to measure us.
        :return: int
        """
        tr = self._tr
        tr.value(0)
        time.sleep_us(5)
        tr.value(1)
        time.sleep_us(10)
        tr.value(0)
        try:
            return machine.time_pulse_us(self._ec, 1, self._to)
        except OSError as e:
            if e.args[0] == 100:  # TIMEOUT
                raise OSError("Object too far")
            raise e

    async def _read(self, temp=None, ignore_errors=False, publish=True) -> float:
        """
        Returns distance in cm.
        Optionally compensated by temperature in °C.
        :return: float
        """
        if temp is None:
            if self._temp is not None:
                temp = await self._temp.temperature(publish=False)
                if temp is None:
                    await _log.asyncLog("warn", "Couldn't read temp sensor, using fallback caluclation")
        val = []
        warnings = 0  # probably not going to happen that both warning types occur at the same time
        warning = "minimum distance reached or different problem"
        for _ in range(20):
            try:
                pt = self._pulse()
                if pt > 175:  # ~3cm, sensor minimum distance, often read although other problems
                    val.append(pt)
                else:
                    warnings += 1
            except OSError as e:
                warning = e
                warnings += 1
            await asyncio.sleep_ms(10)
        if warnings > 10:  # half sensor readings are bad
            if ignore_errors is False:
                await _log.asyncLog("error", "Too many bad sensor readings, error: {!s}".format(warning))
            return None
        # removing extreme values
        val.remove(max(val))
        val.remove(max(val))
        val.remove(min(val))
        val.remove(min(val))
        pt = 0
        for i in range(len(val)):
            pt += val[i]
        pt /= len(val)
        if temp is None:
            dt = (pt / 2) / 29.14
        else:
            dt = (pt / 2) * ((331.5 + (0.6 * temp)) / 10000)
        if dt < 0:
            await _log.asyncLog("warn", "Sensor reading <0")
            return None
        try:
            dt = round(dt, self._pr)
            dt += self._off
        except Exception as e:
            await _log.asyncLog("error", "Error rounding value {!s}".format(dt))
            return dt
        if publish:
            await _mqtt.publish(self._topic, ("{0:." + str(self._pr) + "f}").format(dt))
        return dt

    async def distance(self, temp=None, ignore_errors=False, publish=True) -> float:
        """
        Returns distance in cm, optionally temperature compensated
        :param temp: temperature value for compensation, optional
        :param ignore_errors: prevent bad readings from being published to the log in case the application expects those
        :param publish: if value should be published
        :return:
        """
        return await self._read(temp, ignore_errors, publish)
