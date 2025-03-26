import asyncio
import json
import logging
import time
from collections import deque
import RPi.GPIO as GPIO
from RPLCD.i2c import CharLCD
from lcd_interface import LCDInterface

logger = logging.getLogger(__name__ + ".LCDController")

# Define state constants
class State:
    B_FIELD = 0
    FFT = 1
    ADJUSTING = 2
    OFF = 3

# GPIO Button Pin Configuration
BUTTON_MODE = 17  # B1: Change mode button
BUTTON_POWER = 22  # B2: Power on/off

# Potentiometer Pins (ADC channels)
POT_DAT = 0  # POT1: Data acquisition time potentiometer (ADC channel 0)
POT_FIELD = 1  # POT2: Helmholtz coil adjustment (for future use)

# Display Configuration
LCD_WIDTH = 16
LCD_HEIGHT = 2
I2C_ADDR = 0x27
I2C_BUS = 1

# Data acquisition time constants
MIN_DAT = 0.1  # Minimum data acquisition time (seconds)
MAX_DAT = 100.0  # Maximum data acquisition time (seconds)
DEFAULT_DAT = 1.0  # Default data acquisition time (seconds)

class LCDController(LCDInterface):
    """
    LCD controller that displays B-field and FFT data, with potentiometer control for
    data acquisition time.
    """

    def __init__(self, q_data: asyncio.Queue, q_control: asyncio.Queue):
        """Initialize the LCD controller with data and control queues"""
        self.q_data = q_data
        self.q_control = q_control
        
        # State variables
        self.current_state = State.B_FIELD
        self.display_active = True
        self.adjusting_dat = False
        
        # Data storage
        self.voltage_buffer = deque(maxlen=100)
        self.fft_data = []
        self.last_voltage = 0.0
        self.b_field = 0.0  # Magnetic field in Tesla
        self.data_acquisition_time = DEFAULT_DAT
        self.last_pot_value = 0
        
        # Potentiometer adjustment time tracking
        self.pot_last_change_time = 0
        self.pot_stable_timeout = 1.0  # Time in seconds before applying pot changes
        
        # LCD instance
        self.lcd = None
        
        # Button states for debouncing
        self.button_states = {}
        
        # Conversion factors (to be adjusted based on circuit characteristics)
        self.voltage_to_tesla_factor = 1.0  # Convert voltage to Tesla

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
            GPIO.setup(BUTTON_MODE, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(BUTTON_POWER, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            # Initialize button states (HIGH when not pressed with pull-up)
            self.button_states = { 
                BUTTON_MODE: GPIO.input(BUTTON_MODE),
                BUTTON_POWER: GPIO.input(BUTTON_POWER)
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
                
                for button in [BUTTON_MODE, BUTTON_POWER]:
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

    async def poll_potentiometers(self) -> None:
        """Poll potentiometer values"""
        pot_debounce_value = 5  # Minimum change to register as intentional
        
        while True:
            try:
                # Read POT1 (Data Acquisition Time)
                pot_value = await self.read_potentiometer(POT_DAT)
                
                # Check if potentiometer value has changed significantly
                if abs(pot_value - self.last_pot_value) > pot_debounce_value:
                    logger.debug(f"POT1 value changed: {pot_value} (was {self.last_pot_value})")
                    self.last_pot_value = pot_value
                    self.pot_last_change_time = time.time()
                    
                    # Enter adjusting state if not already in it
                    if self.current_state != State.ADJUSTING and self.display_active:
                        self.current_state = State.ADJUSTING
                        await self.update_display_with_state()
                    
                    # Calculate new data acquisition time using logarithmic scale
                    # Map pot value (0-1023) to data acquisition time (0.1-100s)
                    # t = 0.1 * 10^(pot_value/341)
                    new_dat = MIN_DAT * (10 ** (pot_value / 341.0))
                    self.data_acquisition_time = round(new_dat, 2)
                    
                    # Update display in adjusting state
                    if self.current_state == State.ADJUSTING and self.display_active:
                        await self.display_adjusting_view()
                
                # Check if potentiometer has been stable for a while
                if (self.current_state == State.ADJUSTING and 
                    time.time() - self.pot_last_change_time > self.pot_stable_timeout):
                    # Send new acquisition time to ADC controller
                    await self.send_acquisition_time_update()
                    
                    # Return to previous state
                    self.current_state = State.B_FIELD
                    await self.update_display_with_state()
                
                await asyncio.sleep(0.05)  # Short delay between polls
                
            except Exception as e:
                logger.error(f"Error polling potentiometers: {e}")
                await asyncio.sleep(1)  # Longer delay on error

async def read_potentiometer(self, channel: int) -> int:
    """Read analog value from potentiometer using ADC"""
    try:
        # If we already have voltage data in our buffer, use it
        if self.voltage_buffer:
            # Convert voltage (typically 0-5V) to ADC range (0-1023)
            # Use the latest voltage value from the buffer
            # Channel indicates which value to read if multiple channels exist
            if channel < len(self.last_voltage_values):
                voltage = self.last_voltage_values[channel]
                # Map voltage to potentiometer range (0-1023)
                pot_value = int((voltage / 5.0) * 1023)
                # Ensure value is within range
                return max(0, min(1023, pot_value))
            
        # If no data available yet, return default middle position
        return self.last_pot_value
    except Exception as e:
        logger.error(f"Error reading potentiometer: {e}")
        return self.last_pot_value

    async def send_acquisition_time_update(self) -> None:
        """Send updated data acquisition time to ADC controller"""
        try:
            # Send control message to ADC component to update sampling time
            control_msg = {
                "topic": "adc/command",
                "payload": {
                    "sample_time": self.data_acquisition_time
                }
            }
            await self.q_control.put(control_msg)
            logger.info(f"Sent new acquisition time: {self.data_acquisition_time}s")
        except Exception as e:
            logger.error(f"Error sending acquisition time update: {e}")

    async def handle_button_press(self, button: int) -> None:
        """Handle button press events based on state machine logic"""
        logger.info(f"Handling button press: {button}")
        
        # Prevent actions if both buttons are being pressed simultaneously
        if all(GPIO.input(btn) == 0 for btn in [BUTTON_MODE, BUTTON_POWER] if btn in self.button_states):
            logger.warning("Multiple buttons pressed simultaneously - ignoring")
            return
        
        # Ignore adjustments while in adjusting state
        if self.current_state == State.ADJUSTING and button == BUTTON_MODE:
            logger.info("Ignoring mode button while in ADJUSTING state")
            return
            
        # Power button toggles display from any state
        if button == BUTTON_POWER:
            await self.toggle_power()
            return
            
        # Mode button changes display view when display is on
        if button == BUTTON_MODE and self.display_active:
            if self.current_state == State.B_FIELD:
                self.current_state = State.FFT
                logger.info("Changed view to FFT mode")
            elif self.current_state == State.FFT:
                self.current_state = State.B_FIELD
                logger.info("Changed view to B-field mode")
            
            # Update display based on new state
            await self.update_display_with_state()

    async def toggle_power(self) -> None:
        """Toggle LCD display power on/off"""
        self.display_active = not self.display_active
        
        if self.display_active:
            await asyncio.to_thread(self.lcd.backlight)
            self.current_state = State.B_FIELD  # Reset to default state
            await self.update_display_with_state()
        else:
            await asyncio.to_thread(self.lcd.nobacklight)
            await asyncio.to_thread(self.lcd.clear)

    async def update_display_with_state(self) -> None:
        """Update display based on current state"""
        if not self.display_active:
            return
            
        try:
            if self.current_state == State.B_FIELD:
                await self.display_b_field_view()
            elif self.current_state == State.FFT:
                await self.display_fft_view()
            elif self.current_state == State.ADJUSTING:
                await self.display_adjusting_view()
        except Exception as e:
            logger.error(f"Error updating display: {e}")
            await self.update_display("Display Error", str(e)[:16])

    async def display_b_field_view(self) -> None:
        """Show B-field view with magnetic field reading and acquisition time"""
        # Format B-field in appropriate Tesla units (T, mT, μT)
        b_field_formatted = self.format_magnetic_field(self.b_field)
        
        # Format data acquisition time
        time_str = self.format_time(self.data_acquisition_time)
        
        await self.update_display(f"B: {b_field_formatted}", f"Acq Time: {time_str}")

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

    async def display_adjusting_view(self) -> None:
        """Show adjusting view while potentiometer is being turned"""
        time_str = self.format_time(self.data_acquisition_time)
        await self.update_display("ADJUSTING", f"Acq Time: {time_str}")

    async def update_display(self, line1: str, line2: str) -> None:
        """Update both lines of the LCD display"""
        if not self.display_active or not self.lcd:
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

    def format_magnetic_field(self, value: float) -> str:
        """Format magnetic field value with appropriate unit (T, mT, μT)"""
        abs_value = abs(value)
        if abs_value >= 1:
            return f"{value:.4f} T"
        elif abs_value >= 0.001:
            return f"{value*1000:.2f} mT"
        else:
            return f"{value*1000000:.2f} uT"

    def format_time(self, seconds: float) -> str:
        """Format time value with appropriate unit (s, ms)"""
        if seconds >= 1:
            return f"{seconds:.1f}s"
        else:
            return f"{seconds*1000:.0f}ms"
            
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
            if data_dict["topic"] == "voltage/data":
                if isinstance(data_dict["payload"], list) and len(data_dict["payload"]) > 0:
                    # Store all voltage values for potentiometer reading
                    self.last_voltage_values = data_dict["payload"]
                    
                    # Calculate B-field from voltage
                    voltage = data_dict["payload"][0]
                    self.last_voltage = voltage
                    self.voltage_buffer.append(voltage)
                    self.b_field = self.calculate_b_field(voltage)
                    
                    # Update statistics
                    if self.voltage_buffer:
                        self.min_voltage = min(self.voltage_buffer)
                        self.max_voltage = max(self.voltage_buffer)
                        self.avg_voltage = sum(self.voltage_buffer) / len(self.voltage_buffer)
            
            # Process FFT data
            elif data_dict["topic"] == "fft/data":
                self.fft_data = data_dict["payload"]  # List of [freq, magnitude]
                
                # Calculate peak
                if self.fft_data:
                    self.peak_freq, self.peak_mag = self.calculate_peak(self.fft_data)

            # Update display if not in adjusting state
            if self.current_state != State.ADJUSTING and self.current_state != State.OFF:
                await self.update_display_with_state()

        except Exception as e:
            logger.error(f"Error processing data: {e}")
        
        # Small delay to prevent CPU overload
        await asyncio.sleep(0.01)
            
    async def run(self) -> None:
        """Main run loop"""
        try:
            # Initialize display
            await self.initialize_display()
            
            # Start tasks
            data_task = asyncio.create_task(self.process_data())
            pot_task = asyncio.create_task(self.poll_potentiometers())
            
            # Initial display update
            await self.update_display("Magnetometer", "Ready")
            await asyncio.sleep(1)
            await self.update_display_with_state()
            
            # Create a heartbeat task to ensure system is responsive
            heartbeat_task = asyncio.create_task(self._heartbeat())
            
            # Keep main loop running
            await asyncio.gather(data_task, pot_task, heartbeat_task)
            
        except asyncio.CancelledError:
            logger.info("LCD controller tasks cancelled")
        except Exception as e:
            logger.error(f"LCD controller error: {e}")
        finally:
            await self.cleanup()
            
    async def _heartbeat(self) -> None:
        """Periodic heartbeat to check system health"""
        counter = 0
        while True:
            await asyncio.sleep(10)  # Check every 10 seconds
            counter += 1
            if counter % 6 == 0:  # Log every minute
                logger.info(f"LCD controller heartbeat - State: {self.current_state}, Display: {'ON' if self.display_active else 'OFF'}, DAT: {self.data_acquisition_time}s")
                
            # Check if we've been receiving data
            if counter % 30 == 0:  # Every 5 minutes
                if not self.voltage_buffer and not self.fft_data:
                    logger.warning("No data received for extended period!")
                    # Flash display to indicate issue if display is on
                    if self.display_active:
                        await self.update_display("WARNING", "No data received")
                        await asyncio.sleep(1)
                        await self.update_display_with_state()
            
    async def cleanup(self) -> None:
        """Cleanup GPIO and LCD resources"""
        try:
            if self.lcd:
                await asyncio.to_thread(self.lcd.clear)
                await asyncio.to_thread(self.lcd.close)
            GPIO.cleanup()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
