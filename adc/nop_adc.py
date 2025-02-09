from . import ADCInterface
import asyncio
from collections import deque
import time
import json
import numpy as np
import math

class NopADC(ADCInterface):
    def __init__(self, q_data : asyncio.Queue, N : int = 1000, M : int = 100):
        self.q_data = q_data
        self.N = N
        self.M = M

    async def send_voltage(self, buffer : list[float]) -> None:
        for val in buffer:
            self.q_data.put_nowait(json.dumps({'type': 'voltage', 'val': val}))
    
    async def send_fft(self, data, T) -> None:
        Ntot = len(data)
        FFT = np.abs(np.fft.fft(data))/Ntot   
        V1 = FFT[0:int(Ntot/2+1)]    
        V1[1:-2]=2*V1[1:-2] 
        freq = 1/T*np.linspace(0, int(Ntot/2+1),int(Ntot/2+1))

        self.q_data.put_nowait(json.dumps({'type': 'fft', 'val': [[f, v] for f, v in zip(freq, V1)]}))

    async def run(self) -> None:
        data = deque(maxlen=self.N)
        t0=time.time()
        angle = 0
        counter = 0
        while True:
            counter += 1

            # Sin wave generator
            angle = (angle + (0.01 * 2 * math.pi)) % (2 * math.pi)
            value = math.sin(angle)
            asyncio.create_task(self.send_voltage([value]))
            data.append(value)
            if counter >= self.M and len(data) >= self.N:
                counter = 0
                T = time.time() - t0
                asyncio.create_task(self.send_fft(data, T))
                t0 = time.time()
            await asyncio.sleep(0.001)