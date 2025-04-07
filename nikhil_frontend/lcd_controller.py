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
    def __init__(self, q_data, q_control):
        # Queue for receiving data and sending control messages
        self.q_data = q_data
        self.q_control = q_control
        
        # State variables
        self.current_state = State.B_FIELD
        self.display_active = True
        
        # Display update queue to prevent race conditions
        self.display_queue = asyncio.Queue()
        
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
        
        # Button state management
        self.button_lock = asyncio.Lock()
        self.last_button_time = 0
        self.button_debounce = 0.3  # 300ms debounce
        
        # Coil properties
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
            
            self.lcd.clear()
            logger.info("LCD initialized")
            
            # Show welcome message
            await self.update_display("Magnetometer", "Initializing...")
            
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
                                 callback=self._button_mode_callback, bouncetime=300)
            GPIO.add_event_detect(BUTTON_POWER, GPIO.FALLING, 
                                 callback=self._button_power_callback, bouncetime=300)
            
            logger.info("GPIO setup complete with callbacks")
            
        except Exception as e:
            logger.error(f"GPIO setup failed: {e}")

    def _button_mode_callback(self, channel):
        """Callback for mode button press"""
        current_time = time.time()
        if current_time - self.last_button_time < self.button_debounce:
            return
            
        self.last_button_time = current_time
        
        # Use asyncio to schedule state change safely
        asyncio.create_task(self._handle_mode_button())

    async def _handle_mode_button(self):
        """Safely handle mode button press"""
        async with self.button_lock:
            if not self.display_active:
                return
            
            if self.current_state == State.B_FIELD:
                self.current_state = State.FFT
                logger.info("Switched to FFT view")
            elif self.current_state == State.FFT:
                self.current_state = State.B_FIELD
                logger.info("Switched to B-field view")
            
            # Update display to reflect new state
            await self.update_display_with_state()

    def _button_power_callback(self, channel):
        """Callback for power button press"""
        current_time = time.time()
        if current_time - self.last_button_time < self.button_debounce:
            return
            
        self.last_button_time = current_time
        
        # Use asyncio to schedule power toggle safely
        asyncio.create_task(self._handle_power_button())

    async def _handle_power_button(self):
        """Safely handle power button press"""
        async with self.button_lock:
            # Toggle display
            self.display_active = not self.display_active
            
            if self.display_active:
                logger.info("Display turned ON")
                self.current_state = State.B_FIELD
                await self.update_display_with_state()
            else:
                logger.info("Display turned OFF")
                self.current_state = State.OFF
                await self.update_display("")

    async def update_display(self, line1, line2=""):
        """Thread-safe LCD update method"""
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

    async def update_display_with_state(self):
        """Update display based on current state"""
        if not self.display_active:
            return
            
        if self.current_state == State.B_FIELD:
            # B-field view
            b_field_str = self.format_magnetic_field(self.b_field)
            time_str = self.format_time(self.data_acquisition_time)
            await self.update_display(f"B: {b_field_str}", f"Acq Time: {time_str}")
            
        elif self.current_state == State.FFT:
            # FFT view
            if not self.fft_data:
                await self.update_display("FFT View", "No data yet")
            else:
                peak_freq, peak_mag = self.calculate_peak(self.fft_data)
                await self.update_display(f"Peak: {peak_freq:.1f}Hz", 
                                        f"Mag: {peak_mag:.6f}V")

    def calculate_peak(self, fft_data):
        """Find peak frequency and magnitude in FFT data"""
        if not fft_data:
            return (0.0, 0.0)
            
        # Find the point with maximum magnitude
        return max(fft_data, key=lambda x: x[1])

    async def process_data(self):
        """Process incoming data from queue"""
        try:
            data = await self.q_data.get()
            
            # Handle voltage data
            if data["topic"] == "voltage/data":
                if isinstance(data["payload"], list) and data["payload"]:
                    # Store first voltage value
                    voltage = data["payload"][0]
                    self.voltage_buffer.append(voltage)
                    
                    # Calculate B-field
                    self.b_field = self.calculate_b_field(voltage)
            
            # Handle FFT data
            elif data["topic"] == "fft/data":
                self.fft_data = data["payload"]
            
            # Update display if active and not adjusting
            if self.display_active and self.current_state != State.ADJUSTING:
                await self.update_display_with_state()
                
        except Exception as e:
            logger.error(f"Error processing data: {e}")

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

    async def run(self):
        """Main run method"""
        try:
            # Initialize LCD and GPIO
            await self.initialize_display()
            
            # Main control loop
            while True:
                # Process any incoming data
                if not self.q_data.empty():
                    await self.process_data()
                
                # Small delay to prevent CPU overload
                await asyncio.sleep(0.1)
            
        except asyncio.CancelledError:
            logger.info("LCD controller cancelled")
        except Exception as e:
            logger.error(f"LCD controller error: {e}")
        finally:
            await self.cleanup()

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
