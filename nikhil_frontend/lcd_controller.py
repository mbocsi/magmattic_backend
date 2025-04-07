import asyncio
import logging
import time
import math
from collections import deque
import RPi.GPIO as GPIO
from RPLCD.i2c import CharLCD
from lcd_interface import LCDInterface

logger = logging.getLogger(__name__)

# Define states for our LCD
class State:
    B_FIELD = 0
    FFT = 1
    ADJUSTING = 2
    OFF = 3

# GPIO Pin Configuration
BUTTON_MODE = 17   # Change display mode button
BUTTON_POWER = 22  # Power on/off button

# ADC channels for potentiometers
POT_DAT = 0  # Data acquisition time potentiometer
POT_FIELD = 1  # Helmholtz coil adjustment (not used yet)

# Data acquisition time settings
MIN_DAT = 0.1   # 100ms minimum
MAX_DAT = 100.0  # 100s maximum
DEFAULT_DAT = 1.0  # Default start value

class LCDController(LCDInterface):
    """
    LCD controller for displaying B-field and FFT data
    """
    def __init__(self, q_data, q_control):
        # Queue for receiving data and sending control messages
        self.q_data = q_data
        self.q_control = q_control
        
        # State variables
        self.current_state = State.B_FIELD
        self.display_active = True
        
        # Data storage
        self.voltage_buffer = deque(maxlen=100)
        self.fft_data = None
        self.b_field = 0.0
        self.data_acquisition_time = DEFAULT_DAT
        
        # Potentiometer tracking
        self.last_pot_value = 341  # Middle position by default
        self.pot_last_change = 0
        self.pot_debounce_time = 1.0  # Wait 1 second after last adjustment
        
        # LCD instance
        self.lcd = None
        
        # Tasks for cleanup
        self.tasks = []
        
        # Button debounce
        self.last_button_time = 0
        self.button_debounce = 0.3  # 300ms debounce
        
        # Coil properties (used for B-field calculation)
        self.coil_props = {
            "impedence": 90,
            "windings": 1000,
            "area": 0.01
        }
    
    async def initialize_display(self):
        """Set up the LCD display and GPIO"""
        try:
            # Initialize LCD
            self.lcd = CharLCD(
                i2c_expander="PCF8574",
                address=0x27,
                port=1,
                cols=16,
                rows=2,
                dotsize=8
            )
            
            await asyncio.sleep(0.5)  # Give LCD time to initialize
            self.lcd.clear()
            logger.info("LCD initialized")
            
            # Show welcome message
            self.lcd.write_string("Magnetometer")
            self.lcd.cursor_pos = (1, 0)
            self.lcd.write_string("Initializing...")
            
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"LCD init failed: {e}")
            self._create_dummy_lcd()
        
        # Set up GPIO with callbacks
        self._setup_gpio()
    
    def _create_dummy_lcd(self):
        """Create a fake LCD for testing/when hardware fails"""
        class DummyLCD:
            def __init__(self):
                self.cursor_pos = (0, 0)
                
            def clear(self):
                logger.info("LCD would clear")
                
            def write_string(self, text):
                logger.info(f"LCD would show: {text}")
        
        self.lcd = DummyLCD()
        logger.info("Using dummy LCD")
    
    def _setup_gpio(self):
        """Set up GPIO pins with callbacks"""
        try:
            # Clean up any existing settings
            GPIO.cleanup()
            
            # Set up GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(BUTTON_MODE, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(BUTTON_POWER, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            # Add event detection with callbacks
            GPIO.add_event_detect(BUTTON_MODE, GPIO.FALLING, 
                                 callback=self._button_callback, bouncetime=300)
            GPIO.add_event_detect(BUTTON_POWER, GPIO.FALLING, 
                                 callback=self._button_callback, bouncetime=300)
            
            logger.info("GPIO setup complete with callbacks")
            
        except Exception as e:
            logger.error(f"GPIO setup failed: {e}")
    
    def _button_callback(self, channel):
        """Callback for button presses"""
        # Debounce in software too (sometimes hardware debounce isn't enough)
        current_time = time.time()
        if current_time - self.last_button_time < self.button_debounce:
            return
            
        self.last_button_time = current_time
        
        # We can't directly use asyncio in a callback, so we just set flags
        if channel == BUTTON_MODE:
            # Toggle between B-field and FFT views
            if self.current_state == State.B_FIELD and self.display_active:
                self.current_state = State.FFT
                logger.info("Switched to FFT view")
            elif self.current_state == State.FFT and self.display_active:
                self.current_state = State.B_FIELD
                logger.info("Switched to B-field view")
                
        elif channel == BUTTON_POWER:
            # Toggle display power
            self.display_active = not self.display_active
            if self.display_active:
                logger.info("Display turned ON")
                self.update_display("Display ON", "")
                # Small delay so user can see it turned on
                time.sleep(0.5)
                self.current_state = State.B_FIELD
            else:
                logger.info("Display turned OFF")
                self.current_state = State.OFF
                self.update_display("", "")  # Clear display
    
    async def read_potentiometer(self, channel):
        """Read analog value from potentiometer"""
        # For now, we just use the voltage data that's already read
        # Voltage should range 0-5V, map to 0-1023
        try:
            if hasattr(self, 'last_voltage_values') and self.last_voltage_values:
                if channel < len(self.last_voltage_values):
                    voltage = self.last_voltage_values[channel]
                    pot_value = int((voltage / 5.0) * 1023)
                    return max(0, min(1023, pot_value))
            
            # Return last value if we can't read
            return self.last_pot_value
        except Exception as e:
            logger.error(f"Error reading potentiometer: {e}")
            return self.last_pot_value
    
    def update_display(self, line1, line2):
        """Update the LCD display"""
        if not self.display_active or not self.lcd:
            return
            
        try:
            self.lcd.clear()
            self.lcd.cursor_pos = (0, 0)
            self.lcd.write_string(line1[:16])  # Limit to 16 chars
            
            self.lcd.cursor_pos = (1, 0)
            self.lcd.write_string(line2[:16])
        except Exception as e:
            logger.error(f"Display update error: {e}")
    
    def calculate_peak(self, fft_data):
        """Find peak frequency and magnitude in FFT data"""
        if not fft_data:
            return (0.0, 0.0)
            
        # Find the point with maximum magnitude
        return max(fft_data, key=lambda x: x[1])
    
    def calculate_b_field(self, voltage):
        """Calculate magnetic field strength from voltage"""
        if not self.fft_data:
            # Default to 50Hz if no FFT data
            omega = 2 * math.pi * 50.0
        else:
            # Get frequency from FFT peak
            peak_freq, _ = self.calculate_peak(self.fft_data)
            omega = 2 * math.pi * peak_freq
        
        # Calculate B-field using Faraday's law
        b_field = voltage / (self.coil_props["windings"] * 
                             self.coil_props["area"] * omega)
        
        return b_field
    
    def format_magnetic_field(self, value):
        """Format B-field with appropriate units"""
        abs_value = abs(value)
        if abs_value >= 1:
            return f"{value:.4f} T"
        elif abs_value >= 0.001:
            return f"{value*1000:.2f} mT"
        else:
            return f"{value*1000000:.2f} uT"
    
    def format_time(self, seconds):
        """Format time value with appropriate unit"""
        if seconds >= 1:
            return f"{seconds:.1f}s"
        else:
            return f"{seconds*1000:.0f}ms"
    
    async def process_data(self):
        """Process incoming data from queue"""
        try:
            data = await self.q_data.get()
            
            # Handle voltage data
            if data["topic"] == "voltage/data":
                if isinstance(data["payload"], list) and data["payload"]:
                    # Store all voltage values
                    self.last_voltage_values = data["payload"]
                    
                    # Get first channel value
                    voltage = data["payload"][0]
                    self.voltage_buffer.append(voltage)
                    
                    # Calculate B-field
                    self.b_field = self.calculate_b_field(voltage)
            
            # Handle FFT data
            elif data["topic"] == "fft/data":
                self.fft_data = data["payload"]
            
            # Update display based on state
            if self.display_active and self.current_state != State.ADJUSTING:
                self.update_display_with_state()
                
        except Exception as e:
            logger.error(f"Error processing data: {e}")
    
    async def check_potentiometer(self):
        """Check potentiometer for changes"""
        try:
            # Read POT1 (Data Acquisition Time)
            pot_value = await self.read_potentiometer(POT_DAT)
            
            # Check if value changed significantly
            if abs(pot_value - self.last_pot_value) > 10:
                self.last_pot_value = pot_value
                self.pot_last_change = time.time()
                
                # Enter adjusting state
                if self.current_state != State.ADJUSTING and self.display_active:
                    self.current_state = State.ADJUSTING
                
                # Calculate new data acquisition time (logarithmic)
                new_dat = MIN_DAT * (10 ** (pot_value / 341.0))
                self.data_acquisition_time = min(MAX_DAT, max(MIN_DAT, round(new_dat, 2)))
                
                # Update display in adjusting state
                if self.display_active:
                    self.update_display("ADJUSTING", 
                                      f"Acq Time: {self.format_time(self.data_acquisition_time)}")
            
            # Check if pot has been stable for a while
            elif (self.current_state == State.ADJUSTING and 
                  time.time() - self.pot_last_change > self.pot_debounce_time):
                # Send update to ADC
                await self.send_acquisition_time_update()
                
                # Return to previous state
                self.current_state = State.B_FIELD
                self.update_display_with_state()
                
        except Exception as e:
            logger.error(f"Error checking potentiometer: {e}")
    
    async def send_acquisition_time_update(self):
        """Send updated acquisition time to ADC"""
        try:
            control_msg = {
                "topic": "adc/command",
                "payload": {
                    "sample_time": self.data_acquisition_time
                }
            }
            await self.q_control.put(control_msg)
            logger.info(f"Sent new acquisition time: {self.data_acquisition_time}s")
        except Exception as e:
            logger.error(f"Error sending acquisition time: {e}")
    
    def update_display_with_state(self):
        """Update display based on current state"""
        if not self.display_active:
            return
            
        if self.current_state == State.B_FIELD:
            # B-field view
            b_field_str = self.format_magnetic_field(self.b_field)
            time_str = self.format_time(self.data_acquisition_time)
            self.update_display(f"B: {b_field_str}", f"Acq Time: {time_str}")
            
        elif self.current_state == State.FFT:
            # FFT view
            if not self.fft_data:
                self.update_display("FFT View", "No data yet")
            else:
                peak_freq, peak_mag = self.calculate_peak(self.fft_data)
                self.update_display(f"Peak: {peak_freq:.1f}Hz", 
                                  f"Mag: {peak_mag:.6f}V")
                
        elif self.current_state == State.ADJUSTING:
            # Already handled in check_potentiometer()
            pass
    
    async def recv_control(self):
        """Main control loop - process data and check potentiometer"""
        while True:
            # Process any data in queue
            if not self.q_data.empty():
                await self.process_data()
            
            # Check potentiometer
            await self.check_potentiometer()
            
            # Small delay to prevent CPU overload
            await asyncio.sleep(0.1)
    
    async def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up...")
        
        # Clear LCD
        if self.lcd:
            try:
                self.lcd.clear()
            except:
                pass
        
        # Clean up GPIO
        try:
            GPIO.cleanup()
        except:
            pass
        
        logger.info("Cleanup complete")
    
    async def run(self):
        """Main run method"""
        try:
            # Initialize LCD and GPIO
            await self.initialize_display()
            
            # Show welcome message
            self.update_display("Magnetometer", "Ready")
            await asyncio.sleep(1)
            
            # Start control loop
            await self.recv_control()
            
        except asyncio.CancelledError:
            logger.info("LCD controller cancelled")
        except Exception as e:
            logger.error(f"LCD controller error: {e}")
        finally:
            await self.cleanup()
