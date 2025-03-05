from . import BaseLCDComponent
import asyncio
import logging

logger = logging.getLogger(__name__)


class LCDComponent(BaseLCDComponent):
    def __init__(self, q_data: asyncio.Queue, lcd_config=None):
        super().__init__(q_data, lcd_config)

        from RPLCD.i2c import CharLCD

        self.lcd = CharLCD(
            i2c_expander="PCF8574", address=0x27, port=1, cols=16, rows=2, dotsize=8
        )

    async def update_lcd(self, freq, magnitude) -> None:
        # self.lcd.clear()
        self.lcd.cursor_pos = (0, 0)  # First line, first position
        self.lcd.write_string(f"Freq: {freq:.2f}Hz   ")
        self.lcd.cursor_pos = (1, 0)  # Second line, first position
        self.lcd.write_string(f"Mag: {magnitude:.6f}V")
