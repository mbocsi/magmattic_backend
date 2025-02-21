import asyncio
import json
import logging
import RPi.GPIO as GPIO
from RPLCD.i2c import CharLCD
from . import lcd_config as cfg
from .lcd_interface import LCDInterface

logger = logging.getLogger(__name__ + ".LCDController")

class LCDController(LCDInterface):
    """
    Main LCD controller implementing the LCDInterface.
    Handles display updates and user input through GPIO buttons.
    """
    def __init__(self, q_data: asyncio.Queue, q_control: asyncio.Queue):
        """Initialize the LCD controller with data and control queues"""
        self.q_data = q_data
        self.q_control = q_control
        self.current_menu_index = 0
        self.in_menu = False
        self.current_mode = cfg.DISPLAY_MODES['VOLTAGE']
        self.last_voltage = 0.0
        self.last_fft = [(0, 0)]
        
    async def initialize_display(self) -> None:
        """Initialize LCD and GPIO"""
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(cfg.BUTTON_UP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(cfg.BUTTON_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(cfg.BUTTON_SELECT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(cfg.BUTTON_BACK, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Setup LCD
        try:
            self.lcd = await asyncio.to_thread(
                CharLCD,
                i2c_expander='PCF8574',
                address=cfg.I2C_ADDR,
                port=cfg.I2C_BUS,
                cols=cfg.LCD_WIDTH,
                rows=cfg.LCD_HEIGHT,
                dotsize=8
            )
            logger.info("LCD initialized successfully")
        except Exception as e:
            logger.error(f"LCD initialization failed: {e}")
            raise
            
        # Setup button callbacks
        GPIO.add_event_detect(cfg.BUTTON_UP, GPIO.FALLING, 
            callback=lambda x: asyncio.create_task(self.handle_button_press(cfg.BUTTON_UP)),
            bouncetime=300)
        GPIO.add_event_detect(cfg.BUTTON_DOWN, GPIO.FALLING,
            callback=lambda x: asyncio.create_task(self.handle_button_press(cfg.BUTTON_DOWN)),
            bouncetime=300)
        GPIO.add_event_detect(cfg.BUTTON_SELECT, GPIO.FALLING,
            callback=lambda x: asyncio.create_task(self.handle_button_press(cfg.BUTTON_SELECT)),
            bouncetime=300)
        GPIO.add_event_detect(cfg.BUTTON_BACK, GPIO.FALLING,
            callback=lambda x: asyncio.create_task(self.handle_button_press(cfg.BUTTON_BACK)),
            bouncetime=300)

    async def handle_button_press(self, button: int) -> None:
        """Handle button press events"""
        if self.in_menu:
            if button == cfg.BUTTON_UP:
                self.current_menu_index = (self.current_menu_index - 1) % len(cfg.MENU_ITEMS)
                await self.display_menu()
            elif button == cfg.BUTTON_DOWN:
                self.current_menu_index = (self.current_menu_index + 1) % len(cfg.MENU_ITEMS)
                await self.display_menu()
            elif button == cfg.BUTTON_SELECT:
                await self.select_menu_item()
            elif button == cfg.BUTTON_BACK:
                self.in_menu = False
                await self.update_display_with_data()
        else:
            if button == cfg.BUTTON_SELECT:
                self.in_menu = True
                await self.display_menu()

    async def display_menu(self) -> None:
        """Display the current menu item"""
        menu_item = cfg.MENU_ITEMS[self.current_menu_index]
        await self.update_display(
            f"Menu: {menu_item}",
            "Select or Scroll"
        )

    async def select_menu_item(self) -> None:
        """Handle menu item selection"""
        item = cfg.MENU_ITEMS[self.current_menu_index]
        if item == 'Voltage View':
            self.current_mode = cfg.DISPLAY_MODES['VOLTAGE']
        elif item == 'FFT View':
            self.current_mode = cfg.DISPLAY_MODES['FFT']
        self.in_menu = False
        await self.update_display_with_data()

    async def update_display_with_data(self) -> None:
        """Update display with current data based on mode"""
        if self.current_mode == cfg.DISPLAY_MODES['VOLTAGE']:
            await self.update_display(
                f"Voltage:",
                f"{self.last_voltage:.6f}V"
            )
        else:  # FFT mode
            if self.last_fft:
                freq, mag = self.last_fft[0]
                await self.update_display(
                    f"Peak: {freq:.1f}Hz",
                    f"Mag: {mag:.6f}"
                )

    async def update_display(self, line1: str, line2: str) -> None:
        """Update both lines of the LCD display"""
        try:
            await asyncio.to_thread(self.lcd.clear)
            await asyncio.to_thread(self.lcd.write_string, line1[:cfg.LCD_WIDTH])
            await asyncio.to_thread(self.lcd.cursor_pos, (1, 0))
            await asyncio.to_thread(self.lcd.write_string, line2[:cfg.LCD_WIDTH])
        except Exception as e:
            logger.error(f"Display update failed: {e}")

    async def process_data(self) -> None:
        """Process incoming data from queue"""
        while True:
            try:
                data = await self.q_data.get()
                data_dict = json.loads(data)
                
                if data_dict['type'] == 'voltage':
                    self.last_voltage = data_dict['val'][0]  # Take first value
                elif data_dict['type'] == 'fft':
                    self.last_fft = data_dict['val']  # List of [freq, magnitude]
                
                if not self.in_menu:
                    await self.update_display_with_data()
                    
            except Exception as e:
                logger.error(f"Error processing data: {e}")
            await asyncio.sleep(cfg.UPDATE_INTERVAL)

    async def run(self) -> None:
        """Main run loop"""
        try:
            await self.initialize_display()
            await self.update_display("Magnetometer", "Initializing...")
            await asyncio.sleep(1)
            
            # Start processing data
            data_task = asyncio.create_task(self.process_data())
            
            # Keep the main loop running
            while True:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"LCD controller error: {e}")
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        """Cleanup GPIO and LCD resources"""
        try:
            await asyncio.to_thread(self.lcd.clear)
            await asyncio.to_thread(self.lcd.close)
            GPIO.cleanup()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
