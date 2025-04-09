import asyncio
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

# GPIO Button Pin Configuration - using BCM mode
BUTTON_MODE = 17   # B1: Change mode button
BUTTON_POWER = 22  # B2: Power on/off

# Potentiometer Pins (ADC channels)
POT_DAT = 0  # POT1: Data acquisition time potentiometer (ADC channel 0)

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
        self.button_lock = asyncio.Lock()
        self.last_button_time = 0
        self.button_debounce = 0.2  # seconds
        
        # Data storage
        self.voltage_buffer = deque(maxlen=100)
        self.fft_data = []
        self.last_voltage = 0.0
        self.b_field = 0.0  # Magnetic field in Tesla
        self.data_acquisition_time = DEFAULT_DAT
        self.last_pot_value = 341  # Middle position by default
        self.peak_freq = 0.0
        self.peak_mag = 0.0
        
        # Potentiometer adjustment time tracking
        self.pot_last_change_time = 0
        self.pot_stable_timeout = 1.0  # Time before applying pot changes
        
        # Button state tracking for polling
        self.prev_button_states = {
            BUTTON_MODE: 1,  # Default HIGH with pull-up
            BUTTON_POWER: 1  # Default HIGH with pull-up
        }
        
        # LCD instance
        self.lcd = None
        
        # Display rate limiting
        self.last_display_update = 0
        self.display_update_interval = 0.5  # Update every 0.5 seconds
        
        # Coil properties
        self.coil_props = {
            "impedence": 90,
            "windings": 1000,
            "area": 0.01
        }
    
    async def initialize_display(self) -> None:
        """Initialize the LCD display"""
        try:
            logger.info("Initializing LCD...")
            
            self.lcd = CharLCD(
                i2c_expander="PCF8574",
                address=I2C_ADDR,
                port=I2C_BUS,
                cols=LCD_WIDTH,
                rows=LCD_HEIGHT,
                dotsize=8
            )
            
            # Clear once
            self.lcd.clear()
            
            logger.info("LCD initialized successfully")
            
            # Show welcome message
            await self.update_display("Magnetometer", "Initializing...")
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"LCD initialization failed: {e}")
            self._create_dummy_lcd()
            
        # Setup GPIO buttons
        await self._setup_gpio()
    
    def _create_dummy_lcd(self) -> None:
        """Create a fallback LCD implementation when hardware fails"""
        class DummyLCD:
            def __init__(self):
                self.cursor_pos = (0, 0)
                
            def clear(self):
                logger.info("LCD would clear")
                
            def write_string(self, text):
                logger.info(f"LCD would show: {text}")
        
        self.lcd = DummyLCD()
        logger.info("Using dummy LCD implementation")

    async def _setup_gpio(self) -> None:
        """Set up GPIO buttons using polling only (no edge detection)"""
        try:
            # Clean up any existing GPIO setup first to avoid conflicts
            try:
                GPIO.cleanup()
            except Exception as e:
                logger.info(f"GPIO cleanup initial note: {e}")
                
            # Setup GPIO
            GPIO.setmode(GPIO.BCM)
            
            # Set up buttons with pull-up resistors - simple input only
            GPIO.setup(BUTTON_MODE, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(BUTTON_POWER, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            # Initialize previous button states
            self.prev_button_states[BUTTON_MODE] = GPIO.input(BUTTON_MODE)
            self.prev_button_states[BUTTON_POWER] = GPIO.input(BUTTON_POWER)
            
            logger.info("GPIO setup complete")
            
        except Exception as e:
            logger.error(f"Failed to set up GPIO: {e}")
            logger.info("Continuing without GPIO functionality")

    async def handle_button_press(self, button: int) -> None:
        """Handle button press events based on state machine logic"""
        # Skip if already in an active button press
        current_time = time.time()
        if current_time - self.last_button_time < self.button_debounce:
            return
            
        self.last_button_time = current_time
        
        # Use lock to prevent concurrent state changes
        async with self.button_lock:
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
                
            # Power button toggles display from any state
            elif button == BUTTON_POWER:
                await self.toggle_power()

    async def toggle_power(self) -> None:
        """Toggle LCD display power on/off"""
        try:
            self.display_active = not self.display_active
            
            if self.display_active:
                logger.info("Turning display ON")
                await self.update_display("Display ON", "Resuming...")
                self.current_state = State.B_FIELD  # Reset to default state
                await asyncio.sleep(0.5)
                await self.update_display_with_state()
            else:
                logger.info("Turning display OFF")
                await self.update_display("", "")
                self.current_state = State.OFF
                
        except Exception as e:
            logger.error(f"Error toggling power: {e}")

    async def read_potentiometer(self, channel: int) -> int:
        """Read analog value from potentiometer using Pi-Plates ADC"""
        try:
            # Try to use Pi-Plates ADC
            import piplates.ADCplate as ADC
            # Get a raw voltage reading (0-5V)
            pot_voltage = ADC.getADC(0, channel)  # (board, channel)
            # Convert to a scale of 0-1023
            pot_value = int(pot_voltage * 204.6)  # 1023/5
            # Ensure value is in valid range
            return max(0, min(1023, pot_value))
        except ImportError:
            logger.error("Could not import piplates.ADCplate - using default pot value")
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

    async def update_display(self, line1: str, line2: str) -> None:
        """Update both lines of the LCD display"""
        if not self.display_active or not self.lcd:
            return
        
        try:
            # Clear with adequate delay
            self.lcd.clear()
            await asyncio.sleep(0.05)
            
            # Write first line
            self.lcd.cursor_pos = (0, 0)
            self.lcd.write_string(line1[:LCD_WIDTH])
            
            # Write second line
            self.lcd.cursor_pos = (1, 0)
            self.lcd.write_string(line2[:LCD_WIDTH])
            
            logger.debug(f"Updated display - Line1: '{line1}', Line2: '{line2}'")
            
        except Exception as e:
            logger.error(f"Display update failed: {e}")

    async def update_display_with_state(self) -> None:
        """Update display based on current state"""
        if not self.display_active:
            return
            
        try:
            # Determine lines based on current state
            if self.current_state == State.B_FIELD:
                b_field_formatted = self.format_magnetic_field(self.b_field)
                time_str = self.format_time(self.data_acquisition_time)
                await self.update_display(f"B: {b_field_formatted}", f"Acq Time: {time_str}")
                
            elif self.current_state == State.FFT:
                if not self.fft_data:
                    await self.update_display("FFT View", "No data yet")
                else:
                    peak_freq, peak_mag = self.calculate_peak(self.fft_data)
                    await self.update_display(f"Peak: {peak_freq:.1f}Hz", f"Mag: {peak_mag:.6f}V")
                    
            elif self.current_state == State.ADJUSTING:
                time_str = self.format_time(self.data_acquisition_time)
                await self.update_display("ADJUSTING", f"Acq Time: {time_str}")
                
            else:
                await self.update_display("Unknown State", f"State: {self.current_state}")
        
        except Exception as e:
            logger.error(f"Error updating display with state: {e}")

    def calculate_peak(self, fft_data) -> tuple[float, float]:
        """Calculate the peak frequency and magnitude from FFT data"""
        if not fft_data:
            return (0.0, 0.0)
            
        # Find the point with maximum magnitude
        return max(fft_data, key=lambda x: x[1])
    
    def calculate_b_field(self, voltage: float) -> float:
        """Calculate magnetic field strength (Tesla) using Faraday's law"""
        if not self.fft_data:
            # Default to 50Hz if no FFT data yet
            omega = 2 * 3.14159 * 50.0  # Default angular frequency (ω = 2πf)
        else:
            # Get frequency from FFT peak for more accurate calculation
            peak_freq, _ = self.calculate_peak(self.fft_data)
            omega = 2 * 3.14159 * peak_freq  # Angular frequency ω = 2πf
        
        # Apply Faraday's law: voltage = N * Area * dB/dt
        # For sinusoidal field, B = V / (N * A * ω)
        b_field = voltage / (self.coil_props["windings"] * self.coil_props["area"] * omega)
        
        return b_field

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

    async def process_data_and_buttons(self) -> None:
        """Combined task for processing data and checking buttons"""
        logger.info("Starting main processing loop")
        
        try:
            while True:
                # Check for button presses
                # Read current button states
                try:
                    curr_mode_state = GPIO.input(BUTTON_MODE)
                    curr_power_state = GPIO.input(BUTTON_POWER)
                    
                    # Check for button press (transition from HIGH to LOW with pull-up)
                    if self.prev_button_states[BUTTON_MODE] == GPIO.HIGH and curr_mode_state == GPIO.LOW:
                        logger.info("Mode button pressed (polling)")
                        await self.handle_button_press(BUTTON_MODE)
                        # Add debounce delay
                        await asyncio.sleep(self.button_debounce)
                    
                    if self.prev_button_states[BUTTON_POWER] == GPIO.HIGH and curr_power_state == GPIO.LOW:
                        logger.info("Power button pressed (polling)")
                        await self.handle_button_press(BUTTON_POWER)
                        # Add debounce delay
                        await asyncio.sleep(self.button_debounce)
                    
                    # Update previous states
                    self.prev_button_states[BUTTON_MODE] = curr_mode_state
                    self.prev_button_states[BUTTON_POWER] = curr_power_state
                    
                except Exception as e:
                    logger.error(f"Error reading buttons: {e}")
                
                # Check potentiometer value
                try:
                    pot_value = await self.read_potentiometer(POT_DAT)
                    pot_change = abs(pot_value - self.last_pot_value)
                    
                    # If significant change detected
                    if pot_change > 10:
                        logger.info(f"POT1 value changed: {pot_value} (was {self.last_pot_value})")
                        
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
                            await self.update_display_with_state()
                    
                    # Check if potentiometer has been stable for a while
                    if (self.current_state == State.ADJUSTING and 
                        time.time() - self.pot_last_change_time > self.pot_stable_timeout):
                        # Send new acquisition time to ADC controller
                        await self.send_acquisition_time_update()
                        
                        # Return to previous state
                        self.current_state = State.B_FIELD
                        await self.update_display_with_state()
                        
                except Exception as e:
                    logger.error(f"Error reading potentiometer: {e}")
                
                # Check for queued data if available
                try:
                    if not self.q_data.empty():
                        data = await self.q_data.get()
                        
                        # Process voltage data
                        if data["topic"] == "voltage/data":
                            if isinstance(data["payload"], list) and len(data["payload"]) > 0:
                                # Store voltage values
                                voltage = data["payload"][0]
                                self.last_voltage = voltage
                                self.voltage_buffer.append(voltage)
                                self.b_field = self.calculate_b_field(voltage)
                        
                        # Process FFT data
                        elif data["topic"] == "fft/data":
                            self.fft_data = data["payload"]  # List of [freq, magnitude]
                            
                            # Calculate peak
                            if self.fft_data:
                                self.peak_freq, self.peak_mag = self.calculate_peak(self.fft_data)
                        
                        # Mark as done
                        self.q_data.task_done()
                except asyncio.QueueEmpty:
                    pass
                except Exception as e:
                    logger.error(f"Error processing data: {e}")
                
                # Update display periodically if not in adjusting state
                current_time = time.time()
                if (self.current_state != State.ADJUSTING and 
                    self.current_state != State.OFF and 
                    self.display_active and
                    current_time - self.last_display_update >= self.display_update_interval):
                    await self.update_display_with_state()
                    self.last_display_update = current_time
                
                # Small delay to prevent CPU overload
                await asyncio.sleep(0.05)
                
        except asyncio.CancelledError:
            logger.info("Main processing loop cancelled")
        except Exception as e:
            logger.error(f"Error in main processing loop: {e}")

    async def run(self) -> None:
        """Main run loop"""
        try:
            # Initialize display
            await self.initialize_display()
            
            # Initial display update
            await self.update_display("Magnetometer", "Ready")
            await asyncio.sleep(1)
            await self.update_display_with_state()
            
            # Run the main processing loop - single task for everything
            await self.process_data_and_buttons()
            
        except asyncio.CancelledError:
            logger.info("LCD controller main task cancelled")
        except Exception as e:
            logger.error(f"LCD controller error: {e}")
        finally:
            # Clean up
            await self.cleanup()
    
    async def cleanup(self) -> None:
        """Cleanup all resources"""
        logger.info("Cleaning up LCD controller resources...")
        
        # Display final message
        if self.lcd and self.display_active:
            try:
                await self.update_display("Shutdown", "Complete")
                await asyncio.sleep(0.5)
                self.lcd.clear()
            except Exception as e:
                logger.error(f"Error during LCD cleanup: {e}")
        
        # Clean up GPIO
        try:
            GPIO.cleanup()
        except Exception as e:
            logger.error(f"Error during GPIO cleanup: {e}")
        
        logger.info("Cleanup complete")
