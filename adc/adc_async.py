import piplates.ADCplate as ADC
from piplates.ADCplate import * # type: ignore (this package is stupid)
import asyncio

def getStream(addr):
    events = None
    while(True):
        while not ADC.check4EVENTS(addr):
            pass
        events = ADC.getEVENTS(addr)
        if events and events & 0x80:    
            break                  
    return ADC.getSTREAM(addr)

async def getStreamSync(addr):
     return await asyncio.to_thread(getStream, addr)

async def readSingleSync(addr : int, pin : str):
        return await asyncio.to_thread(ADC.readSINGLE, addr, pin)

