"""
Extending the ADCplate library for use with synchronous python
"""

import piplates.ADCplate as ADC
from piplates.ADCplate import *  # type: ignore
import asyncio


async def getStreamSync(addr) -> list[float]:
    events = None
    while True:
        while not ADC.check4EVENTS(addr):
            await asyncio.sleep(0.001)
        events = ADC.getEVENTS(addr)
        if events and events & 0x80:
            break
    return ADC.getSTREAM(addr)  # type: ignore (this package infers int)
