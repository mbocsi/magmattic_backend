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


    
    async def send_voltage(self, buffer : list[int]) -> None:
        for val in buffer:
            self.q_data.put_nowait(json.dumps({'type': 'voltage', 'val': val}))
    
    async def send_fft(self, data, T) -> None:
        Ntot = len(data)   # Total number of readings 
            
        FFT = np.abs(np.fft.fft(data))/Ntot   # Compute abs value of FFT in volts. Double sided
        # Convert to single sided voltage:
        # You must convert Ntot/2_+1 into an integer for it to work with the indices of an array, because its by default a float
        V1 = FFT[0:int(Ntot/2+1)]    # First half is for positive frequency. See this article for more details: https://selfnoise.co.uk/resources/signals-and-dft/dft-even-odd-n/
        # The indicies will change slightly depending on if you have an even or odd number of data points in the time domain
        V1[1:-2]=2*V1[1:-2] # Multiply by 2 except for DC component and Nyquist frequency. -1 represents the end of the array at the Nyquist frequency

        freq = 1/T*np.linspace(0, int(Ntot/2+1),int(Ntot/2+1))   # Frequency axis in Hz

        self.q_data.put_nowait(json.dumps({'type': 'fft', 'val': [[f, v] for f, v in zip(freq, V1)]}))


    
    async def run(self) -> None:
        logger.info("running adc controller")
        adc_id = self.ADC.getID(self.addr)
        if not adc_id:
            raise Exception(f"Failed to connect to ADC at addr={self.addr}")
        logger.info(f"connected ADC-> id={adc_id}")
        self.ADC.setMODE(self.addr,'ADV')  
        self.ADC.configINPUT(self.addr, self.pin, self.sample_rate, True)

        data : deque[int] = deque([], maxlen=self.N)
        t0=time.time()
        while True:
            try:
                # voltage = self.ADC.readSINGLE(self.addr,self.pin)
                voltage = 0
                logger.debug(f"ADC reading: {voltage}")
                if not voltage:
                    logger.warning("reading from ADC stream was None")
                    continue
                # await self.send_voltage([voltage])
                data.append(voltage)   

                # if self.ADC.check4EVENTS(self.addr) and (self.ADC.getEVENTS(self.addr) or 0) & 0x80 and len(data) >= self.N:
                #     T = time.time() - t0
                #     await self.send_fft(data, T)
                #     t0 = time.time()
            except Exception as e:
                logger.warning(f"An exception has occured when reading ADC stream: {e}")
            await asyncio.sleep(0.001)