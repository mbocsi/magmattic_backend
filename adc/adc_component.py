from . import BaseADCComponent
import asyncio
import logging

logger = logging.getLogger(__name__)

SAMPLE_CONV = {
    1.25: 0,
    2.5: 1,
    5: 2,
    10: 3,
    16.67: 4,
    20: 5,
    25: 6,
    50: 7,
    59.98: 8,
    100.2: 9,
    200.3: 10,
    381: 11,
    504: 12,
    1007: 13,
    2597: 14,
    5208: 15,
    10415: 16,
    15625: 17,
    31250: 18,
}


class ADCComponent(BaseADCComponent):
    def __init__(
        self,
        pub_queue: asyncio.Queue,
        sub_queue: asyncio.Queue,
        addr: int = 0,
        pin: str = "D0",
        sample_rate: int = 1007,
        Nbuf: int = 32,
    ):
        super().__init__(
            pub_queue=pub_queue,
            sub_queue=sub_queue,
            addr=addr,
            pin=pin,
            sample_rate=sample_rate,
            Nbuf=Nbuf,
        )

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

        # TODO: Test this section
        if self.sample_rate not in SAMPLE_CONV:
            self.sample_rate = 1007
            self.pub_queue.put_nowait(
                {"topic": "adc/status", "payload": self.getStatus()}
            )

        self.ADC.setMODE(self.addr, "ADV")
        self.ADC.configINPUT(self.addr, self.pin, SAMPLE_CONV[self.sample_rate], True)
        self.ADC.startSTREAM(self.addr, self.Nbuf)
        try:
            while True:
                buffer = await self.ADC.getStreamSync(self.addr)
                logger.debug(f"ADC buffer readings: {buffer}")
                self.send_voltage(buffer)
                await asyncio.sleep(0)  # Guarantee resource release to event runtime
        except asyncio.CancelledError:
            logger.debug("stream_adc() was cancelled")
        except Exception as e:
            logger.warning(f"stream_adc() threw an exception: {e}")
        finally:
            self.ADC.stopSTREAM(self.addr)
