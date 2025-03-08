import asyncio
import json
import logging
import RPi.GPIO as GPIO
from RPLCD.i2c import CharLCD
import lcd_config as cfg
from lcd_interface import LCDInterface

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
        self.current_mode = cfg.DISPLAY_MODES["VOLTAGE"]
        self.last_voltage = 0.0
        self.last_fft = [(0, 0)]
        self.lcd = None
        self.lcd_power = True
        self.counter = 0  # For testing button presses

    async def initialize_display(self) -> None:
        """Initialize LCD and GPIO"""
        # Setup LCD first
        try:
            self.lcd = await asyncio.to_thread(
                CharLCD,
                i2c_expander="PCF8574",
                address=cfg.I2C_ADDR,
                port=cfg.I2C_BUS,
                cols=cfg.LCD_WIDTH,
                rows=cfg.LCD_HEIGHT,
                dotsize=8,
            )
            
            logger.info("LCD initialized successfully")
            
            # Test display output
            await asyncio.to_thread(self.lcd.clear)
            await asyncio.to_thread(self.lcd.write_string, "LCD Test")
            await asyncio.to_thread(lambda: setattr(self.lcd, 'cursor_pos', (1, 0)))
            await asyncio.to_thread(self.lcd.write_string, "Working!")
            
        except Exception as e:
            logger.error(f"LCD initialization failed: {e}")
            raise

        # Create a shared queue for button events
        self.button_queue = asyncio.Queue()
        
        # Simple callback that just puts button into queue
        def button_callback(channel):
            try:
                # This runs in a separate thread from asyncio
                # Use threadsafe method to communicate with asyncio
                loop = asyncio.get_event_loop()
                asyncio.run_coroutine_threadsafe(self.button_queue.put(channel), loop)
                logger.info(f"Button press on channel {channel}")
            except Exception as e:
                logger.error(f"Button callback error: {e}")

        # Try to setup GPIO, but continue even if it fails
        try:
            # Clean up any existing GPIO setup
            try:
                GPIO.cleanup()
            except:
                pass
            
            # Setup GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(cfg.BUTTON_UP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(cfg.BUTTON_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(cfg.BUTTON_SELECT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(cfg.BUTTON_BACK, GPIO.IN, pull_up_down=GPIO.PUD_UP)

       
            # Instead of using edge detection, set up polling
            logger.info("Setting up GPIO polling instead of edge detection")
            self.button_states = { 
            cfg.BUTTON_UP: GPIO.input(cfg.BUTTON_UP),
            cfg.BUTTON_DOWN: GPIO.input(cfg.BUTTON_DOWN),
            cfg.BUTTON_SELECT: GPIO.input(cfg.BUTTON_SELECT),
            cfg.BUTTON_BACK: GPIO.input(cfg.BUTTON_BACK)
            }
            # Start button polling task
            asyncio.create_task(self.poll_buttons())
                except Exception as e:
                    logger.error(f"Failed to set up GPIO: {e}")
                    logger.info("Continuing without GPIO functionality")

    async def process_button_presses(self) -> None:
        """Process button presses from the queue"""
        while True:
            try:
                # Wait for button press events from the queue
                channel = await self.button_queue.get()
                # Now handle the button press in the asyncio context
                await self.handle_button_press(channel)
            except Exception as e:
                logger.error(f"Error processing button press: {e}")
            # Short sleep to prevent CPU hogging
            await asyncio.sleep(0.01)

    async def handle_button_press(self, button: int) -> None:
        """Handle button press events"""
        logger.info(f"Handling button press: {button}")
        
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
            # When not in menu, handle counter for testing
            if button == cfg.BUTTON_UP:
                self.counter += 1
                await self.update_display(f"Counter: {self.counter}", "Press SELECT:Menu")
            elif button == cfg.BUTTON_DOWN and self.counter > 0:
                self.counter -= 1
                await self.update_display(f"Counter: {self.counter}", "Press SELECT:Menu")
            elif button == cfg.BUTTON_SELECT:
                self.in_menu = True
                await self.display_menu()

    async def display_menu(self) -> None:
        """Display the current menu item"""
        menu_item = cfg.MENU_ITEMS[self.current_menu_index]
        # Show menu position indicator
        position = f"{self.current_menu_index+1}/{len(cfg.MENU_ITEMS)}"
        await self.update_display(f"Menu: {menu_item}", position)

    async def select_menu_item(self) -> None:
        """Handle menu item selection"""
        item = cfg.MENU_ITEMS[self.current_menu_index]
        if item == "Voltage View":
            self.current_mode = cfg.DISPLAY_MODES["VOLTAGE"]
            self.in_menu = False
            await self.update_display_with_data()
        elif item == "FFT View":
            self.current_mode = cfg.DISPLAY_MODES["FFT"]
            self.in_menu = False
            await self.update_display_with_data()
        elif item == "Settings":
            await self.update_display("Settings", "Not implemented")
            await asyncio.sleep(2)
            await self.display_menu()
        elif item == "Power Off LCD":
            await self.toggle_power()

    async def toggle_power(self) -> None:
        """Toggle LCD power on/off"""
        self.lcd_power = not self.lcd_power
        if self.lcd_power:
            await asyncio.to_thread(self.lcd.backlight)
            await self.update_display_with_data()
        else:
            await asyncio.to_thread(self.lcd.nobacklight)
        self.in_menu = False

    async def update_display_with_data(self) -> None:
        """Update display with current data based on mode"""
        if not self.lcd_power:
            return
            
        if self.current_mode == cfg.DISPLAY_MODES["VOLTAGE"]:
            await self.update_display(f"Voltage:", f"{self.last_voltage:.6f}V")
        else:  # FFT mode
            if self.last_fft:
                freq, mag = self.last_fft[0]
                await self.update_display(f"Peak: {freq:.1f}Hz", f"Mag: {mag:.6f}")

    async def update_display(self, line1: str, line2: str) -> None:
        """Update both lines of the LCD display"""
        if not self.lcd_power or not self.lcd:
            return
            
        try:
            await asyncio.to_thread(self.lcd.clear)
            await asyncio.to_thread(self.lcd.write_string, line1[:cfg.LCD_WIDTH])
            await asyncio.to_thread(lambda: setattr(self.lcd, 'cursor_pos', (1, 0)))
            await asyncio.to_thread(self.lcd.write_string, line2[:cfg.LCD_WIDTH])
        except Exception as e:
            logger.error(f"Display update failed: {e}")

    async def process_data(self) -> None:
        """Process incoming data from queue"""
        while True:
            try:
                data = await self.q_data.get()
                
                # Handle both string and dict data formats
                if isinstance(data, str):
                    try:
                        data_dict = json.loads(data)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON data: {data}")
                        continue
                else:
                    data_dict = data

                if data_dict["type"] == "voltage":
                    self.last_voltage = data_dict["val"][0]  # Take first value
                elif data_dict["type"] == "fft":
                    self.last_fft = data_dict["val"]  # List of [freq, magnitude]

                if not self.in_menu:
                    await self.update_display_with_data()

            except Exception as e:
                logger.error(f"Error processing data: {e}")
            await asyncio.sleep(cfg.UPDATE_INTERVAL)

    async def run(self) -> None:
        """Main run loop"""
        try:
            await self.initialize_display()
            await asyncio.sleep(1)  # Let the test message display briefly
            
            # Initial display
            await self.update_display("Magnetometer", "Press SELECT:Menu")
            
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
            if self.lcd:
                await asyncio.to_thread(self.lcd.clear)
                await asyncio.to_thread(self.lcd.close)
            GPIO.cleanup()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
