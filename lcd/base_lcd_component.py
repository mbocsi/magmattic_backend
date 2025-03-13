import asyncio
from app_interface import AppComponent
from abc import abstractmethod
import logging

logger = logging.getLogger(__name__)


class BaseLCDComponent(AppComponent):
    def __init__(self, sub_queue: asyncio.Queue, lcd_config=None):
        self.sub_queue = sub_queue
        self.lcd_config = lcd_config
        if lcd_config is None:
            self.lcd_config = {
                "i2c_expander": "PCF8574",
                "address": 0x27,
                "port": 1,
                "cols": 16,
                "rows": 2,
                "dotsize": 8,
            }

    def calculate_peak(self, fft_data: dict) -> tuple[float, float]:
        return max(fft_data, key=lambda x: x[1])

    async def read_data(self) -> None:
        while True:
            try:
                data = await self.sub_queue.get()
                await self.update_lcd(*self.calculate_peak(data["payload"]))
            except Exception as e:
                logger.warning(f"An exception occured when reading data: {e}")

    async def run(self) -> None:
        logger.info("starting lcd")
        data_task = asyncio.create_task(self.read_data())
        await data_task

    @abstractmethod
    async def update_lcd(self, freq, magnitude) -> None: ...
