import asyncio
import json
import logging
import time
from collections import deque
import RPi.GPIO as GPIO
from RPLCD.i2c import CharLCD
from lcd_interface import LCDInterface

logger = logging.getLogger(__name__ + ".LCDController")

# Define view modes
VIEW_MODES = {
    'VOLTAGE': 0,
    'FFT': 1,
    'MULTI_FREQ': 2,
    'STATS': 3
}

# GPIO Button Pins (from lcd_config.py)
BUTTON_UP = 17
BUTTON_DOWN = 27
BUTTON_SELECT = 22
BUTTON_BACK = 23
POWER_SWITCH = 24

# LCD Configuration
LCD_WIDTH = 16
LCD_HEIGHT = 2
I2C_ADDR = 0x27
I2C_BUS = 1

class LCDController(LCDInterface):
    """
    Improved LCD controller that shows different views of ADC data.
    """

    def __init__(self, q_data: asyncio.Queue, q_control: asyncio.Queue):
        """Initialize the LCD controller with data and control queues"""
        self.q_data = q_data
        self.q_control = q_control
        
        # Menu and display states
        self.in_menu = False
        self.current_menu_index = 0
        self.current_view_mode = VIEW_MODES['VOLTAGE']
        self.lcd_power = True
        
        # Data storage
        self.voltage_buffer = deque(maxlen=100)
        self.fft_data = []
        self.last_voltage = 0.0
        self.min_voltage = 0.0
        self.max_voltage = 0.0
        self.avg_voltage = 0.0
        
        # Menu options
        self.menu_options = [
            "1. Voltage View",
            "2. FFT View",
            "3. Multi-Freq View",
            "4. Stats View"
        ]
        
        # Character LCD instance
        self.lcd = None
        
        # Custom characters for bar graph
        self.custom_chars = [
            bytearray([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F]),  # 1/5 bar
            bytearray([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F, 0x1F]),  # 2/5 bar
            bytearray([0x00, 0x00, 0x00, 0x00, 0x00, 0x1F, 0x1F, 0x1F]),  # 3/5 bar
            bytearray([0x00, 0x00, 0x00, 0x00, 0x1F, 0x1F, 0x1F, 0x1F]),  # 4/5 bar
            bytearray([0x00, 0x00, 0x00, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F]),  # 5/5 bar
            bytearray([0x00, 0x00, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F]),  # 6/5 bar
            bytearray([0x00, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F]),  # 7/5 bar
            bytearray([0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F]),  # Full bar
        ]

    async def initialize_display(self) -> None:
        """Initialize the LCD display and GPIO pins"""
        try:
            # Initialize LCD
            self.lcd = await asyncio.to_thread(
                CharLCD,
                i2c_expander="PCF8574",
                address=I2C_ADDR,
                port=I2C_BUS,
                cols=LCD_WIDTH,
                rows=LCD_HEIGHT,
                dotsize=8,
            )
            
            # Create custom characters for bar graph
            for i, char in enumerate(self.custom_chars):
                await asyncio.to_thread(self.lcd.create_char, i, char)
            
            logger.info("LCD initialized successfully")
            
            # Show welcome message
            await self.update_display("Magnetometer", "Initializing...")
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"LCD initialization failed: {e}")
            # Create a fallback text-only LCD
            self._create_dummy_lcd()
        
        # Setup GPIO buttons
        await self._setup_gpio()

    def _create_dummy_lcd(self) -> None:
        """Create a fallback LCD implementation when hardware fails"""
        class DummyLCD:
            def clear(self):
                logger.info("LCD would clear")
                
            def write_string(self, text):
                logger.info(f"LCD would show: {text}")
                
            def close(self):
                logger.info("LCD would close")
                
            def backlight(self):
                logger.info("LCD backlight on")
                
            def nobacklight(self):
                logger.info("LCD backlight off")
                
            def create_char(self, location, bitmap):
                pass
                
        self.lcd = DummyLCD()
        logger.info("Using dummy LCD implementation")

    async def _setup_gpio(self) -> None:
        """Set up GPIO buttons with polling approach"""
        try:
            # Clean up any existing GPIO setup
            try:
                GPIO.cleanup()
            except:
                pass
            
            # Setup GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(BUTTON_UP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(BUTTON_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(BUTTON_SELECT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(BUTTON_BACK, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(POWER_SWITCH, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            # Initialize button states (HIGH when not pressed with pull-up)
            self.button_states = { 
                BUTTON_UP: GPIO.input(BUTTON_UP),
                BUTTON_DOWN: GPIO.input(BUTTON_DOWN),
                BUTTON_SELECT: GPIO.input(BUTTON_SELECT),
                BUTTON_BACK: GPIO.input(BUTTON_BACK),
                POWER_SWITCH: GPIO.input(POWER_SWITCH)
            }
            
            # Start button polling task
            asyncio.create_task(self.poll_buttons())
            logger.info("GPIO polling setup complete")
            
        except Exception as e:
            logger.error(f"Failed to set up GPIO: {e}")
            logger.info("Continuing without GPIO functionality")
            self.button_states = {}  # Empty dict to indicate no buttons

    async def poll_buttons(self) -> None:
        """Poll buttons for state changes with debouncing"""
        debounce_time = 0.2  # seconds
        last_press_time = time.time()
        
        while True:
            try:
                current_time = time.time()
                
                # Skip debounce period
                if current_time - last_press_time < debounce_time:
                    await asyncio.sleep(0.01)
                    continue
                
                button_pressed = False
                
                for button in [BUTTON_UP, BUTTON_DOWN, BUTTON_SELECT, BUTTON_BACK, POWER_SWITCH]:
                    # Skip if button doesn't exist in our state dict
                    if button not in self.button_states:
                        continue
                        
                    current_state = GPIO.input(button)
                    previous_state = self.button_states[button]
                    
                    # Button press detected (HIGH to LOW transition with pull-up)
                    if previous_state == 1 and current_state == 0:
                        logger.info(f"Button press detected on pin {button}")
                        await self.handle_button_press(button)
                        button_pressed = True
                        last_press_time = current_time  # Reset debounce timer
                    
                    # Update state
                    self.button_states[button] = current_state
                
                # Short delay between polls
                await asyncio.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Error polling buttons: {e}")
                await asyncio.sleep(1)  # Longer delay on error

    async def handle_button_press(self, button: int) -> None:
        """Handle button press events"""
        logger.info(f"Handling button press: {button}")
        
        # Power button toggles backlight from anywhere
        if button == POWER_SWITCH:
            await self.toggle_power()
            return
            
        # Skip if LCD is powered off
        if not self.lcd_power:
            return
            
        if self.in_menu:
            # Handle navigation in the menu
            if button == BUTTON_UP:
                self.current_menu_index = (self.current_menu_index - 1) % len(self.menu_options)
                await self.display_menu()
            elif button == BUTTON_DOWN:
                self.current_menu_index = (self.current_menu_index + 1) % len(self.menu_options)
                await self.display_menu()
            elif button == BUTTON_SELECT:
                # Set the view mode based on menu selection
                self.current_view_mode = self.current_menu_index
                self.in_menu = False
                await self.update_display_with_data()
            elif button == BUTTON_BACK:
                # Exit menu without changing view
                self.in_menu = False
                await self.update_display_with_data()
        else:
            # When not in menu
            if button == BUTTON_SELECT:
                # Enter menu
                self.in_menu = True
                await self.display_menu()
            elif button == BUTTON_BACK:
                # Cycle through views
                self.current_view_mode = (self.current_view_mode + 1) % len(VIEW_MODES)
                await self.update_display_with_data()

    async def toggle_power(self) -> None:
        """Toggle LCD backlight on/off"""
        self.lcd_power = not self.lcd_power
        if self.lcd_power:
            await asyncio.to_thread(self.lcd.backlight)
            await self.update_display_with_data()
        else:
            await asyncio.to_thread(self.lcd.nobacklight)

    async def display_menu(self) -> None:
        """Display the view selection menu"""
        option = self.menu_options[self.current_menu_index]
        position = f"{self.current_menu_index+1}/{len(self.menu_options)}"
        await self.update_display(f">{option}", position)

    async def update_display_with_data(self) -> None:
        """Update display based on current view mode"""
        if not self.lcd_power:
            return
            
        try:
            if self.current_view_mode == VIEW_MODES['VOLTAGE']:
                await self.display_voltage_view()
            elif self.current_view_mode == VIEW_MODES['FFT']:
                await self.display_fft_view()
            elif self.current_view_mode == VIEW_MODES['MULTI_FREQ']:
                await self.display_multi_freq_view()
            elif self.current_view_mode == VIEW_MODES['STATS']:
                await self.display_stats_view()
        except Exception as e:
            logger.error(f"Error updating display: {e}")
            await self.update_display("Display Error", str(e)[:16])

    async def display_voltage_view(self) -> None:
        """Show voltage view with real-time reading and bar graph"""
        voltage_str = f"Voltage: {self.last_voltage:.4f}V"
        
        # Create bar graph based on voltage
        # Assuming voltage range of 0-5V for full scale
        bar_length = min(int(abs(self.last_voltage) / 5.0 * 16), 16)
        bar = ""
        for i in range(bar_length):
            if i < 8:
                bar += chr(7)  # Use the full-block character
            else:
                bar += "="  # Use = for the rest
        
        bar = bar.ljust(16)  # Fill with spaces to 16 chars
        
        await self.update_display(voltage_str, bar)

    async def display_fft_view(self) -> None:
        """Show FFT view with peak frequency and magnitude"""
        if not self.fft_data:
            await self.update_display("FFT View", "No data yet")
            return
            
        # Find peak frequency and magnitude
        peak_freq, peak_mag = self.calculate_peak(self.fft_data)
        
        freq_str = f"Peak: {peak_freq:.1f}Hz"
        mag_str = f"Mag: {peak_mag:.6f}V"
        
        await self.update_display(freq_str, mag_str)

    async def display_multi_freq_view(self) -> None:
        """Show multiple frequency peaks"""
        if not self.fft_data or len(self.fft_data) < 2:
            await self.update_display("Multi-Freq View", "Insufficient data")
            return
            
        # Sort FFT data by magnitude and get top 2 peaks
        sorted_fft = sorted(self.fft_data, key=lambda x: x[1], reverse=True)
        
        # Skip DC component (0 Hz) if present
        peaks = []
        for freq, mag in sorted_fft:
            if freq > 0.5:  # Skip near-DC
                peaks.append((freq, mag))
                if len(peaks) >= 2:
                    break
        
        if len(peaks) < 2:
            # Not enough peaks found
            await self.update_display("Multi-Freq View", "Need more peaks")
            return
            
        f1, m1 = peaks[0]
        f2, m2 = peaks[1]
        
        freq_str = f"F1:{f1:.1f} F2:{f2:.1f}"
        mag_str = f"M1:{m1:.4f} M2:{m2:.4f}"
        
        await self.update_display(freq_str, mag_str)

    async def display_stats_view(self) -> None:
        """Show voltage statistics"""
        if not self.voltage_buffer:
            await self.update_display("Statistics", "No data yet")
            return
            
        # Calculate statistics
        stats_str = "Min/Max/Avg"
        values_str = f"{self.min_voltage:.2f}/{self.max_voltage:.2f}/{self.avg_voltage:.2f}"
        
        await self.update_display(stats_str, values_str)

    async def update_display(self, line1: str, line2: str) -> None:
        """Update both lines of the LCD display"""
        if not self.lcd_power or not self.lcd:
            return
            
        try:
            await asyncio.to_thread(self.lcd.clear)
            await asyncio.to_thread(self.lcd.write_string, line1[:LCD_WIDTH])
            await asyncio.to_thread(lambda: setattr(self.lcd, 'cursor_pos', (1, 0)))
            await asyncio.to_thread(self.lcd.write_string, line2[:LCD_WIDTH])
        except Exception as e:
            logger.error(f"Display update failed: {e}")

    def calculate_peak(self, fft_data) -> tuple[float, float]:
        """Calculate the peak frequency and magnitude from FFT data"""
        if not fft_data:
            return (0.0, 0.0)
            
        # Find the point with maximum magnitude
        return max(fft_data, key=lambda x: x[1])

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

                # Process voltage data
                if data_dict["type"] == "voltage":
                    if isinstance(data_dict["val"], list) and len(data_dict["val"]) > 0:
                        voltage = data_dict["val"][0]
                        self.last_voltage = voltage
                        self.voltage_buffer.append(voltage)
                        
                        # Update statistics
                        if self.voltage_buffer:
                            self.min_voltage = min(self.voltage_buffer)
                            self.max_voltage = max(self.voltage_buffer)
                            self.avg_voltage = sum(self.voltage_buffer) / len(self.voltage_buffer)
                
                # Process FFT data
                elif data_dict["type"] == "fft":
                    self.fft_data = data_dict["val"]  # List of [freq, magnitude]

                # Update display if not in menu
                if not self.in_menu:
                    await self.update_display_with_data()

            except Exception as e:
                logger.error(f"Error processing data: {e}")
            
            # Small delay to prevent CPU overload
            await asyncio.sleep(0.1)

    async def run(self) -> None:
        """Main run loop"""
        try:
            await self.initialize_display()
            await asyncio.sleep(1)  # Show initialize message briefly
            
            # Start processing data
            data_task = asyncio.create_task(self.process_data())
            
            # Initial display
            await self.update_display("Magnetometer", "Ready")
            await asyncio.sleep(1)
            await self.update_display_with_data()
            
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
