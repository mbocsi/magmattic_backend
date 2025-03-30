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

# Debug mode for additional logging
DEBUG_MODE = True

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
        self.last_voltage_values = []  # Store all voltage channels
        self.b_field = 0.0  # Magnetic field in Tesla
        self.data_acquisition_time = DEFAULT_DAT
        self.last_pot_value = 341  # Middle position by default
        self.peak_freq = 0.0
        self.peak_mag = 0.0
        
        # Potentiometer adjustment time tracking
        self.pot_last_change_time = 0
        self.pot_stable_timeout = 1.0  # Time in seconds before applying pot changes
        
        # LCD instance
        self.lcd = None
        
        # Button states for debouncing
        self.button_states = {}
        
        # Display rate limiting
        self.last_display_update = 0
        self.display_update_interval = 0.5  # Update at most every 0.5 seconds
        
        # Conversion factors (to be adjusted based on circuit characteristics)
        self.voltage_to_tesla_factor = 1.0  # Convert voltage to Tesla
        
        # Coil properties (from Marton's code)
        self.coil_props = {
            "impedence": 90,
            "windings": 1000,
            "area": 0.01
        }

    async def initialize_display(self) -> None:
        """Initialize the LCD display and GPIO pins"""
        try:
            # Initialize LCD
            logger.info("Initializing LCD...")
            
            # Create LCD with a thread to prevent blocking
            self.lcd = await asyncio.to_thread(
                CharLCD,
                i2c_expander="PCF8574",
                address=I2C_ADDR,
                port=I2C_BUS,
                cols=LCD_WIDTH,
                rows=LCD_HEIGHT,
                dotsize=8,
                # Some LCDs work better with specific charmaps
                charmap='A00' 
            )
            
            # Give the LCD time to initialize and stabilize
            await asyncio.sleep(0.5)
            
            # Clear the display a few times to reset any lingering state
            for _ in range(3):
                await asyncio.to_thread(self.lcd.clear)
                await asyncio.sleep(0.1)
                
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
            
        # Give the dummy LCD a cursor_pos property that can be set
        # This avoids attributes errors in the rest of the code
        class DummyLCDWithCursor(DummyLCD):
            def __init__(self):
                self.cursor_pos = (0, 0)
                
        self.lcd = DummyLCDWithCursor()
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
        debounce_time = 0.3  # seconds - increased for better stability
        last_press_time = time.time()
        
        while True:
            try:
                current_time = time.time()
                
                # Skip debounce period
                if current_time - last_press_time < debounce_time:
                    await asyncio.sleep(0.05)
                    continue
                
                button_pressed = False
                
                for button in [BUTTON_MODE, BUTTON_POWER]:
                    # Skip if button doesn't exist in our state dict
                    if button not in self.button_states:
                        continue
                        
                    # Take multiple readings to ensure stability
                    readings = []
                    for _ in range(3):
                        readings.append(GPIO.input(button))
                        await asyncio.sleep(0.01)
                    
                    # Use majority vote to determine current state
                    current_state = 1 if sum(readings) >= 2 else 0
                    previous_state = self.button_states[button]
                    
                    # Button press detected (HIGH to LOW transition with pull-up)
                    if previous_state == 1 and current_state == 0:
                        logger.info(f"Button press detected on pin {button}")
                        await self.handle_button_press(button)
                        button_pressed = True
                        last_press_time = current_time  # Reset debounce timer
                    
                    # Update state
                    self.button_states[button] = current_state
                
                # Longer delay between polls to reduce CPU usage
                await asyncio.sleep(0.05)
                
            except asyncio.CancelledError:
                logger.info("Button polling task cancelled")
                break
            except Exception as e:
                logger.error(f"Error polling buttons: {e}")
                await asyncio.sleep(1)  # Longer delay on error

    async def test_buttons(self) -> None:
        """Test button states and responsiveness"""
        logger.info("Testing button states...")
        
        for button in [BUTTON_MODE, BUTTON_POWER]:
            if button not in self.button_states:
                logger.warning(f"Button {button} not configured")
                continue
                
            # Read current state
            state = GPIO.input(button)
            logger.info(f"Button {button} state: {'HIGH (not pressed)' if state else 'LOW (pressed)'}")
            
        logger.info("Button test complete")

    async def poll_potentiometers(self) -> None:
        """Poll potentiometer values"""
        pot_debounce_value = 20  # Increased threshold to prevent noise from triggering changes
        
        while True:
            try:
                # Read POT1 (Data Acquisition Time)
                pot_value = await self.read_potentiometer(POT_DAT)
                
                # Check if potentiometer value has changed significantly
                if abs(pot_value - self.last_pot_value) > pot_debounce_value:
                    if DEBUG_MODE:
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
                        await self.display_adjusting_view()
                
                # Check if potentiometer has been stable for a while
                if (self.current_state == State.ADJUSTING and 
                    time.time() - self.pot_last_change_time > self.pot_stable_timeout):
                    # Send new acquisition time to ADC controller
                    await self.send_acquisition_time_update()
                    
                    # Return to previous state
                    self.current_state = State.B_FIELD
                    await self.update_display_with_state()
                
                await asyncio.sleep(0.1)  # Longer delay between polls
                
            except asyncio.CancelledError:
                logger.info("Potentiometer polling task cancelled")
                break
            except Exception as e:
                logger.error(f"Error polling potentiometers: {e}")
                await asyncio.sleep(1)  # Longer delay on error

    async def read_potentiometer(self, channel: int) -> int:
        """Read analog value from potentiometer using ADC"""
        try:
            # If we already have voltage data in our buffer, use it
            if hasattr(self, 'last_voltage_values') and self.last_voltage_values:
                # Check if we have data for the requested channel
                if channel < len(self.last_voltage_values):
                    voltage = self.last_voltage_values[channel]
                    # Map voltage (0-5V) to potentiometer range (0-1023)
                    pot_value = int((voltage / 5.0) * 1023)
                    # Ensure value is within range
                    return max(0, min(1023, pot_value))
            
            # If no data available yet, return last known value
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
        try:
            self.display_active = not self.display_active
            
            if self.display_active:
                logger.info("Turning display ON")
                # Just clear and update - don't use backlight which may not be supported
                await asyncio.to_thread(self.lcd.clear)
                self.current_state = State.B_FIELD  # Reset to default state
                await self.update_display_with_state()
            else:
                logger.info("Turning display OFF")
                await asyncio.to_thread(self.lcd.clear)
        except Exception as e:
            logger.error(f"Error toggling power: {e}")

    async def update_display_with_state(self) -> None:
        """Update display based on current state with rate limiting"""
        if not self.display_active:
            return
            
        # Rate limit display updates
        current_time = time.time()
        if current_time - self.last_display_update < self.display_update_interval:
            return
            
        self.last_display_update = current_time
            
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
        
        if DEBUG_MODE:
            logger.info(f"Displaying B-field: {b_field_formatted}, Time: {time_str}")
        
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
        
        if DEBUG_MODE:
            logger.info(f"Displaying FFT: {freq_str}, {mag_str}")
        
        await self.update_display(freq_str, mag_str)

    async def display_adjusting_view(self) -> None:
        """Show adjusting view while potentiometer is being turned"""
        time_str = self.format_time(self.data_acquisition_time)
        
        if DEBUG_MODE:
            logger.info(f"Displaying Adjusting: Time: {time_str}")
            
        await self.update_display("ADJUSTING", f"Acq Time: {time_str}")

    async def update_display(self, line1: str, line2: str) -> None:
        """Update both lines of the LCD display with proper timing"""
        if not self.display_active or not self.lcd:
            return
            
        try:
            # Clear with adequate delay
            await asyncio.to_thread(self.lcd.clear)
            await asyncio.sleep(0.05)  # Wait for clear to finish
            
            # Write first line
            await asyncio.to_thread(self.lcd.write_string, line1[:LCD_WIDTH])
            await asyncio.sleep(0.02)  # Short delay between operations
            
            # Position cursor for second line
            await asyncio.to_thread(lambda: setattr(self.lcd, 'cursor_pos', (1, 0)))
            await asyncio.sleep(0.02)  # Short delay
            
            # Write second line
            await asyncio.to_thread(self.lcd.write_string, line2[:LCD_WIDTH])
            
            if DEBUG_MODE:
                logger.debug(f"Updated display - Line1: '{line1}', Line2: '{line2}'")
        except Exception as e:
            logger.error(f"Display update failed: {e}")

    def calculate_peak(self, fft_data) -> tuple[float, float]:
        """Calculate the peak frequency and magnitude from FFT data"""
        if not fft_data:
            return (0.0, 0.0)
            
        # Find the point with maximum magnitude
        return max(fft_data, key=lambda x: x[1])
    
    def calculate_b_field(self, voltage: float) -> float:
        """Calculate magnetic field strength (Tesla) using Faraday's law
        
        Based on Marton's implementation from calculation_component.py
        """
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
                        
                        if DEBUG_MODE and len(self.voltage_buffer) % 10 == 0:
                            logger.debug(f"Voltage: {voltage:.3f}V, B-field: {self.format_magnetic_field(self.b_field)}")
                
                # Process FFT data
                elif data_dict["topic"] == "fft/data":
                    self.fft_data = data_dict["payload"]  # List of [freq, magnitude]
                    
                    # Calculate peak
                    if self.fft_data:
                        self.peak_freq, self.peak_mag = self.calculate_peak(self.fft_data)
                        if DEBUG_MODE and random.random() < 0.1:  # Log occasionally to avoid flooding
                            logger.debug(f"FFT Peak: {self.peak_freq:.1f}Hz, Magnitude: {self.peak_mag:.6f}V")

                # Update display if not in adjusting state
                if self.current_state != State.ADJUSTING and self.current_state != State.OFF:
                    await self.update_display_with_state()

            except asyncio.CancelledError:
                logger.info("Data processing task cancelled")
                break
            except Exception as e:
                logger.error(f"Error processing data: {e}")
            
            # Small delay to prevent CPU overload
            await asyncio.sleep(0.01)
            
    async def run(self) -> None:
        """Main run loop"""
        try:
            # Initialize display
            await self.initialize_display()
            
            # Test button states at startup
            if DEBUG_MODE:
                await self.test_buttons()
            
            # Start tasks
            data_task = asyncio.create_task(self.process_data())
            pot_task = asyncio.create_task(self.poll_potentiometers())
            
            # Initial display update
            await self.update_display("Magnetometer", "Ready")
            await asyncio.sleep(1)
            await self.update_display_with_state()
            
            # Create a heartbeat task to ensure system is responsive
            heartbeat_task = asyncio.create_task(self._heartbeat())
            
            # Keep main tasks running
            all_tasks = [data_task, pot_task, heartbeat_task]
            
            # Wait for tasks to complete (they shouldn't normally)
            await asyncio.gather(*all_tasks)
            
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
                logger.info(f"LCD heartbeat - State: {self.current_state}, Display: {'ON' if self.display_active else 'OFF'}, DAT: {self.data_acquisition_time}s")
                
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
                logger.info("Cleaning up LCD and GPIO resources...")
                await asyncio.to_thread(self.lcd.clear)
                await asyncio.sleep(0.1)  # Give it time to complete
                await asyncio.to_thread(lambda: setattr(self.lcd, 'cursor_pos', (0, 0)))
                await asyncio.sleep(0.1)  # Give it time to complete
                await asyncio.to_thread(self.lcd.write_string, "Shutdown         ")
                await asyncio.sleep(0.1)  # Give it time to complete
                await asyncio.to_thread(lambda: setattr(self.lcd, 'cursor_pos', (1, 0)))
                await asyncio.sleep(0.1)  # Give it time to complete
                await asyncio.to_thread(self.lcd.write_string, "Complete         ")
                await asyncio.sleep(0.5)  # Give it time to display
                
                # Final clear
                await asyncio.to_thread(self.lcd.clear)
                await asyncio.sleep(0.1)
                await asyncio.to_thread(getattr(self.lcd, 'close', lambda: None))
            
            # Clean up GPIO
            try:
                GPIO.cleanup()
            except:
                pass
                
            logger.info("Cleanup complete")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
