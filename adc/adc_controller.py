from . import ADCInterface
import asyncio
import json
import time
import numpy as np 
from collections import deque
import logging

logger = logging.getLogger(__name__ + ".ADCController")

class ADCController(ADCInterface):
    def __init__(self, q_data : asyncio.Queue, addr: int = 0, pin : str = 'D0', sample_rate : int = 13, N : int = 1000, M : int = 1):
        import piplates.ADCplate as ADC

        self.ADC = ADC

        self.q_data = q_data

        self.addr = addr
        self.pin = pin
        self.sample_rate = sample_rate
        self.M = 1
        self.N = N # Number of samples used for the FFT

        adc_id = self.ADC.getID(self.addr)
        if not adc_id:
            raise Exception(f"Failed to connect to ADC at addr={self.addr}")
        logger.info(f"connected ADC-> id={adc_id}")

    
    async def send_voltage(self, val : float) -> None:
            self.q_data.put_nowait(json.dumps({'type': 'voltage', 'val': val}))
    
    async def send_fft(self, data, T) -> None:
        Ntot = len(data)
            
        FFT = np.abs(np.fft.fft(data))/Ntot
        V1 = FFT[0:int(Ntot/2+1)]
        V1[1:-2]=2*V1[1:-2]

        freq = 1/T*np.linspace(0, int(Ntot/2+1),int(Ntot/2+1))

        self.q_data.put_nowait(json.dumps({'type': 'fft', 'val': [[f, v] for f, v in zip(freq, V1)]}))

    async def readSINGLE_async(self):
        return await asyncio.to_thread(self.ADC.readSINGLE, self.addr, self.pin)
    
    async def run(self) -> None:
        logger.info("running adc controller")
        self.ADC.setMODE(self.addr,'ADV')  
        self.ADC.configINPUT(self.addr, self.pin, self.sample_rate, True)

        data : deque[int] = deque([], maxlen=self.N)
        t0=time.time()
        while True:
            try:
                voltage = await self.readSINGLE_async() 
                logger.debug(f"ADC reading: {voltage}")
                if voltage is None:
                    logger.warning("reading from ADC stream was None")
                    raise Exception("voltage is None")
                asyncio.create_task(self.send_voltage(voltage))
                data.append(voltage)   

                # if self.ADC.check4EVENTS(self.addr) and (self.ADC.getEVENTS(self.addr) or 0) & 0x80 and len(data) >= self.N:
                #     T = time.time() - t0
                #     await self.send_fft(data, T)
                #     t0 = time.time()
            except Exception as e:
                logger.warning(f"An exception has occured when reading ADC stream: {e}")
            finally:
                await asyncio.sleep(0)