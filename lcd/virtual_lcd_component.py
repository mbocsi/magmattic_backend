from . import BaseLCDComponent
import aiofiles
import logging

logger = logging.getLogger(__name__)


class VirtualLCDComponent(BaseLCDComponent):
    async def update_lcd(self, freq, magnitude) -> None:
        async with aiofiles.open("virtual_lcd.txt", "w") as f:
            await f.write(f"Freq: {freq:.2f}Hz\n")
            await f.write(f"Mag: {magnitude:.6f}V")
