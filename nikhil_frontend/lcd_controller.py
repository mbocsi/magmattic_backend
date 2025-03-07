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
    Enhanced LCD controller implementing the LCDInterface.
    Handles display updates and user input through GPIO buttons.
    Provides menu navigation and data display.
    """

    def __init__(self, q_data: asyncio.Queue, q_control: asyncio.Queue):
        """Initialize the LCD controller with data and control queues"""
        self.q_data = q_data
        self.q_control = q_control
        
        # Menu and display state
        self.current_menu_index = 0
        self.in_menu = False
        self.current_mode = cfg.DISPLAY_MODES["VOLTAGE"]
        self.lcd_power = True
        
        # Data storage
        self.last_voltage = 0.0
        self.peak_frequency = 0.0
        self.peak_magnitude = 0.0
        self.fft_data = []
        
        # Display formatting
        self.voltage_format = "V: {:.6f}V"
        self.freq_format = "F: {:.2f}Hz"
        self.mag_format = "M: {:.6f}V"
        
        # For testing
        self.counter = 0

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

    # Try to setup GPIO, but continue even if it fails
    try:
        # Clean up any existing GPIO setup
        GPIO.cleanup()
        
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(cfg.BUTTON_UP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(cfg.BUTTON_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(cfg.BUTTON_SELECT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(cfg.BUTTON_BACK, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Define a callback handler function
        def button_callback(channel):
            asyncio.create_task(self.handle_button_press(channel))

        # Setup button callbacks individually with error handling for each
        try:
            GPIO.add_event_detect(
                cfg.BUTTON_UP,
                GPIO.FALLING,
                callback=button_callback,
                bouncetime=300,
            )
            logger.info("UP button configured successfully")
        except Exception as e:
            logger.error(f"Failed to set up UP button: {e}")

        try:
            GPIO.add_event_detect(
                cfg.BUTTON_DOWN,
                GPIO.FALLING,
                callback=button_callback,
                bouncetime=300,
            )
            logger.info("DOWN button configured successfully")
        except Exception as e:
            logger.error(f"Failed to set up DOWN button: {e}")

        try:
            GPIO.add_event_detect(
                cfg.BUTTON_SELECT,
                GPIO.FALLING,
                callback=button_callback,
                bouncetime=300,
            )
            logger.info("SELECT button configured successfully")
        except Exception as e:
            logger.error(f"Failed to set up SELECT button: {e}")

        try:
            GPIO.add_event_detect(
                cfg.BUTTON_BACK,
                GPIO.FALLING,
                callback=button_callback,
                bouncetime=300,
            )
            logger.info("BACK button configured successfully")
        except Exception as e:
            logger.error(f"Failed to set up BACK button: {e}")
            
    except Exception as e:
        logger.error(f"Failed to set up GPIO: {e}")
        logger.info("Continuing without GPIO functionality")

    async def handle_button_press(self, button: int) -> None:
        """Handle button press events"""
        logger.debug(f"Button press detected: {button}")
        
        # Ignore button presses if LCD is powered off
        if not self.lcd_power:
            if button == cfg.BUTTON_SELECT and hasattr(cfg, 'POWER_SWITCH'):
                await self.toggle_power()
            return
            
        if self.in_menu:
            # Menu navigation logic
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
            # Main display logic
            if button == cfg.BUTTON_SELECT:
                self.in_menu = True
                await self.display_menu()
            elif button == cfg.BUTTON_UP:
                # For testing: increment counter
                self.counter += 1
                await self.update_display(f"Counter: {self.counter}", "SELECT for menu")

    async def toggle_power(self) -> None:
        """Toggle LCD power state"""
        self.lcd_power = not self.lcd_power
        logger.info(f"LCD power toggled: {'ON' if self.lcd_power else 'OFF'}")
        
        if self.lcd_power:
            await asyncio.to_thread(self.lcd.backlight)
            await self.update_display_with_data()
        else:
            await asyncio.to_thread(self.lcd.clear)
            await asyncio.to_thread(self.lcd.nobacklight)

    async def display_menu(self) -> None:
        """Display the current menu item"""
        menu_item = cfg.MENU_ITEMS[self.current_menu_index]
        position = f"[{self.current_menu_index+1}/{len(cfg.MENU_ITEMS)}]"
        await self.update_display(f"> {menu_item}", position)

    async def select_menu_item(self) -> None:
        """Handle menu item selection based on the selected menu item"""
        menu_item = cfg.MENU_ITEMS[self.current_menu_index]
        
        if menu_item == "Voltage View":
            self.current_mode = cfg.DISPLAY_MODES["VOLTAGE"]
            self.in_menu = False
            await self.update_display_with_data()
        
        elif menu_item == "FFT View":
            self.current_mode = cfg.DISPLAY_MODES["FFT"]
            self.in_menu = False
            await self.update_display_with_data()
        
        elif menu_item == "Settings":
            # Display settings submenu
            await self.update_display("Settings:", "Not implemented")
            await asyncio.sleep(2)
            await self.display_menu()
        
        elif menu_item == "Info":
            # Display magnetometer info
            await self.update_display("Magnetometer", "V1.0 ECE Capstone")
            await asyncio.sleep(2)
            await self.display_menu()

    async def update_display_with_data(self) -> None:
        """Update display with current data based on selected mode"""
        if not self.lcd_power:
            return
            
        if self.current_mode == cfg.DISPLAY_MODES["VOLTAGE"]:
            voltage_str = self.voltage_format.format(self.last_voltage)
            await self.update_display("Voltage Reading:", voltage_str)
        
        elif self.current_mode == cfg.DISPLAY_MODES["FFT"]:
            freq_str = self.freq_format.format(self.peak_frequency)
            mag_str = self.mag_format.format(self.peak_magnitude)
            await self.update_display(freq_str, mag_str)

    async def update_display(self, line1: str, line2: str) -> None:
        """Update both lines of the LCD display"""
        if not self.lcd_power:
            return
            
        try:
            
            
            # Update display content
            await asyncio.to_thread(self.lcd.clear)
            await asyncio.to_thread(lambda: setattr(self.lcd, 'cursor_pos', (0, 0)))
            await asyncio.to_thread(self.lcd.write_string, line1[:cfg.LCD_WIDTH])
            await asyncio.to_thread(lambda: setattr(self.lcd, 'cursor_pos', (1, 0)))
            await asyncio.to_thread(self.lcd.write_string, line2[:cfg.LCD_WIDTH])
        except Exception as e:
            logger.error(f"Display update failed: {e}")

    async def find_peak_fft(self, fft_data):
        """Find peak frequency and magnitude from FFT data"""
        if not fft_data:
            return 0.0, 0.0
            
        # Find the data point with highest magnitude
        peak_point = max(fft_data, key=lambda x: x[1])
        return peak_point[0], peak_point[1]  # frequency, magnitude

    async def process_data(self) -> None:
        """Process incoming data from queue"""
        while True:
            try:
                data = await self.q_data.get()
                
                # Check if data is string (from Marton's code) or dict (from tests)
                if isinstance(data, str):
                    data_dict = json.loads(data)
                else:
                    data_dict = data
                
                if data_dict["type"] == "voltage":
                    # Extract voltage data - use first value if multiple
                    self.last_voltage = data_dict["val"][0] if isinstance(data_dict["val"], list) else data_dict["val"]
                
                elif data_dict["type"] == "fft":
                    # Store FFT data and extract peak
                    self.fft_data = data_dict["val"]
                    self.peak_frequency, self.peak_magnitude = await self.find_peak_fft(self.fft_data)
                
                # Update display if not in menu
                if not self.in_menu and self.lcd_power:
                    await self.update_display_with_data()
                    
            except Exception as e:
                logger.error(f"Error processing data: {e}")
            
            # Add small delay to prevent event loop blocking
            await asyncio.sleep(cfg.UPDATE_INTERVAL)

    async def run(self) -> None:
        """Main run loop"""
        try:
            # Initialize hardware
            await self.initialize_display()
            
            # Show welcome message
            await self.update_display("Magnetometer", "Initializing...")
            await asyncio.sleep(1)
            
            # Start processing data
            data_task = asyncio.create_task(self.process_data())
            
            # Show ready message
            await self.update_display("Ready", "SELECT for menu")
            
            # Keep the main loop running
            while True:
                await asyncio.sleep(0.1)
        
        except Exception as e:
            logger.error(f"LCD controller error: {e}")
        
        finally:
            # Ensure cleanup runs
            await self.cleanup()

    async def cleanup(self) -> None:
        """Cleanup GPIO and LCD resources"""
        try:
            if hasattr(self, 'lcd'):
                await asyncio.to_thread(self.lcd.clear)
                await asyncio.to_thread(self.lcd.close)
            GPIO.cleanup()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
