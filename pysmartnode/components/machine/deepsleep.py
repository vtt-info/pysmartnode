'''
Created on 2018-07-16

@author: Kevin Köck
'''

"""
example config:
{
    package: .machine.deepsleep
    component: deepsleep
    constructor_args: {
        sleeping_time: 10    # sleeping time in seconds (float value ok)
        wait_before_sleep: null # optional, wait this many seconds before going to deepsleep
        # event: null       # optional, asyncio event to wait for before going to sleep  
    }
}
"""

__version__ = "0.1"
__updated__ = "2018-07-16"

import machine
import uasyncio as asyncio
from sys import platform


async def deepsleep(sleeping_time, wait_before_sleep=None, event=None):
    if wait_before_sleep is not None:
        await asyncio.sleep(wait_before_sleep)
    if event is not None:
        await event
    if platform == "esp32_LoBo":
        machine.deepsleep(int(sleeping_time * 1000))
    else:
        rtc = machine.RTC()
        rtc.irq(trigger=rtc.ALARM0, wake=machine.DEEPSLEEP)
        rtc.alarm(rtc.ALARM0, int(sleeping_time * 1000))
        machine.deepsleep()
