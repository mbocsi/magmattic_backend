from . import BaseADCComponent
import asyncio
import numpy as np
from collections import deque
import logging

logger = logging.getLogger(__name__ + ".ADCController")


class ADCComponent(BaseADCComponent):
    def __init__(
        self,
        q_data: asyncio.Queue,
        q_control: asyncio.Queue,
        addr: int = 0,
        pin: str = "D0",
        sample_rate: int = 13,
        N: int = 16,
        M: int = 1000,
    ):
        super().__init__(q_data, q_control, addr, pin, sample_rate, N, M)

        import adc.adc_async as ADC

        self.ADC = ADC

        adc_id = self.ADC.getID(self.addr)
        if not adc_id:
            logger.error(f"Failed to connect to ADC at addr={self.addr}")
        else:
            logger.info(f"connected ADC-> id={adc_id}")

    async def stream_adc(self):
        """
        Runs the ADC sampling process
        """

        logger.debug("stream_adc() started")
        self.ADC.setMODE(self.addr, "ADV")
        self.ADC.configINPUT(self.addr, self.pin, self.sample_rate, True)
        self.ADC.startSTREAM(self.addr, self.N)
        data: deque[float] = deque([], maxlen=self.M)
        try:
            while True:
                buffer = await self.ADC.getStreamSync(self.addr)
                logger.debug(f"ADC buffer readings: {buffer}")
                await self.send_voltage(buffer)
                data.extend(buffer)

                if len(data) >= self.M:
                    T = self.M / 1000
                    await self.send_fft(list(data), T)
                    if not self.rolling_fft:
                        data.clear()
                await asyncio.sleep(0)  # Guarentee resource release to event runtime
        except asyncio.CancelledError:
            logger.debug("stream_adc() was cancelled")
        except Exception as e:
            logger.warning("stream_adc() threw an exception:", e)
        finally:
            self.ADC.stopSTREAM(self.addr)
