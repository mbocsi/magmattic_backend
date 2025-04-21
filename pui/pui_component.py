import asyncio
import numpy as np
import logging
import time
from collections import deque

from RPLCD.i2c import CharLCD
from app_interface import AppComponent
import piplates.ADCplate as ADC
from .pui_config import *

logger = logging.getLogger(__name__)


class PUIComponent(AppComponent):
    """
    LCD controller that displays B-field and FFT data, with potentiometer control for
    data acquisition time.
    """

    def __init__(self, q_data: asyncio.Queue, q_control: asyncio.Queue):
        """Initialize the LCD controller with data and control queues"""
        import RPi.GPIO as GPIO

        self.GPIO = GPIO

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
        self.freq = 0.0
        self.data_acquisition_time = DEFAULT_DAT
        self.last_pot_value = 500  # Middle position by default
        self.peak_freq = 0.0
        self.peak_mag = 0.0

        # Potentiometer adjustment time tracking
        self.pot_last_change_time = 0
        self.pot_stable_timeout = 1.0  # Time before applying pot changes

        # LCD instance
        self.lcd = None

        # Display rate limiting
        self.last_display_update = 0
        self.display_update_interval = 0.5  # Update every 0.5 seconds

        # Coil properties
        self.coil_props = {"impedence": 90, "windings": 1000, "area": 0.01}

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
                dotsize=8,
            )

            # Clear once
            self.lcd.clear()

            logger.info("LCD initialized successfully")

            # Get initial potentiometer reading for DAT
            try:
                raw_value = ADC.getADC(0, POT_DAT)
                pot_value = min(1023, int(raw_value * 1023 / 5.0))
                self.last_pot_value = pot_value

                # Set initial DAT based on potentiometer position
                self.data_acquisition_time = MIN_DAT * (10 ** (pot_value / 341.0))
                self.data_acquisition_time = round(self.data_acquisition_time, 2)
                logger.info(
                    f"Initial potentiometer value: {pot_value}, DAT: {self.data_acquisition_time}s"
                )
            except Exception as e:
                logger.error(f"Failed to read initial potentiometer value: {e}")

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
        """Set up GPIO buttons with polling approach"""
        try:
            # GPIO mode is already set globally at the top of the file

            # Use polling instead of edge detection for more reliability
            self.GPIO.setup(BUTTON_MODE, self.GPIO.IN, pull_up_down=self.GPIO.PUD_UP)
            self.GPIO.setup(BUTTON_POWER, self.GPIO.IN, pull_up_down=self.GPIO.PUD_UP)

            logger.info("GPIO setup complete")

        except Exception as e:
            logger.error(f"Failed to set up GPIO: {e}")
            logger.info("Continuing without GPIO functionality")

    async def poll_buttons(self) -> None:
        """Poll buttons for state changes with debouncing"""
        logger.info("Button polling task started")

        prev_mode_state = self.GPIO.input(BUTTON_MODE)
        prev_power_state = self.GPIO.input(BUTTON_POWER)

        try:
            while True:
                # Read current button states
                mode_state = self.GPIO.input(BUTTON_MODE)
                power_state = self.GPIO.input(BUTTON_POWER)

                # Check for mode button press (HIGH to LOW with pull-up)
                if prev_mode_state == self.GPIO.HIGH and mode_state == self.GPIO.LOW:
                    logger.info("Mode button pressed")
                    await self.handle_button_press(BUTTON_MODE)
                    await asyncio.sleep(self.button_debounce)  # Debounce

                # Check for power button press
                if prev_power_state == self.GPIO.HIGH and power_state == self.GPIO.LOW:
                    logger.info("Power button pressed")
                    await self.handle_button_press(BUTTON_POWER)
                    await asyncio.sleep(self.button_debounce)  # Debounce

                # Update previous states
                prev_mode_state = mode_state
                prev_power_state = power_state

                # Small delay between polling cycles
                await asyncio.sleep(0.05)

        except asyncio.CancelledError:
            logger.info("Button polling task cancelled")
        except Exception as e:
            logger.error(f"Error polling buttons: {e}")

    async def poll_potentiometer(self) -> None:
        """Poll potentiometer values and update DAT accordingly"""
        logger.info("Potentiometer polling task started")
        pot_debounce_value = 10  # Threshold to prevent noise

        try:
            while True:
                try:
                    # Direct ADC reading - exactly like simple_lcd_test.py
                    raw_value = ADC.getADC(0, POT_DAT)
                    pot_value = min(1023, int(raw_value * 1023 / 5.0))

                    # Check if potentiometer value has changed significantly
                    if abs(pot_value - self.last_pot_value) > pot_debounce_value:
                        logger.info(
                            f"POT1 value changed: {pot_value}, voltage: {raw_value:.2f}V"
                        )

                        self.last_pot_value = pot_value
                        self.pot_last_change_time = time.time()

                        # Enter adjusting state if not already in it and display is active
                        if (
                            self.current_state != State.ADJUSTING
                            and self.display_active
                        ):
                            self.current_state = State.ADJUSTING

                        # Calculate new data acquisition time using logarithmic scale
                        # Map pot value (0-1023) to data acquisition time (0.1-100s)
                        # t = 0.1 * 10^(pot_value/341)
                        new_dat = MIN_DAT * (10 ** (pot_value / 341.0))
                        self.data_acquisition_time = round(new_dat, 2)

                        # Update display in adjusting state
                        if self.display_active:
                            time_str = self.format_time(self.data_acquisition_time)
                            await self.update_display(
                                "ADJUSTING", f"Acq Time: {time_str}"
                            )

                    # Check if potentiometer has been stable for a while
                    if (
                        self.current_state == State.ADJUSTING
                        and time.time() - self.pot_last_change_time
                        > self.pot_stable_timeout
                    ):
                        # Send new acquisition time to ADC controller
                        await self.send_acquisition_time_update()

                        # Return to previous state
                        self.current_state = State.B_FIELD
                        await self.update_display_with_state()

                except Exception as e:
                    logger.error(f"Error reading potentiometer: {e}")

                # Delay between polls
                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info("Potentiometer polling task cancelled")
        except Exception as e:
            logger.error(f"Error in potentiometer polling task: {e}")

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

    async def send_acquisition_time_update(self) -> None:
        """Send updated data acquisition time to ADC controller"""
        try:
            # Send control message to ADC component to update sampling parameters
            control_msg = {
                "topic": "calculation/command",
                "payload": {"acquisition_time": self.data_acquisition_time},
            }
            await self.q_control.put(control_msg)
            logger.info(
                f"Sent new acquisition time: {self.data_acquisition_time}s (sample rate: {control_msg['payload']['acquisition_time']})"
            )
        except Exception as e:
            logger.error(f"Error sending acquisition time update: {e}")

    async def process_data(self) -> None:
        """Process incoming data from queue"""
        logger.info("Data processing task started")

        try:
            while True:
                data = await self.q_data.get()

                try:
                    # Process voltage data
                    if data["topic"] == "signal/data":
                        self.last_voltage = data["payload"]["mag"]
                        bfield_vector = np.array(data["payload"]["bfield"])
                        self.b_field = np.linalg.norm(bfield_vector)
                        self.freq = data["payload"]["freq"]

                    # Update display if not in adjusting state
                    if (
                        self.current_state != State.ADJUSTING
                        and self.current_state != State.OFF
                        and self.display_active
                    ):
                        await self.update_display_with_state()

                except Exception as e:
                    logger.error(f"Error processing data: {e}")

                # Mark this task as done
                self.q_data.task_done()

                # Small delay to prevent CPU overload
                await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            logger.info("Data processing task cancelled")
        except Exception as e:
            logger.error(f"Error in data processing task: {e}")

    async def update_display(self, line1: str, line2: str) -> None:
        """Update both lines of the LCD display without clearing"""
        if not self.display_active or not self.lcd:
            return

        try:
            line1 = line1.ljust(LCD_WIDTH)[:LCD_WIDTH]
            line2 = line2.ljust(LCD_WIDTH)[:LCD_WIDTH]

            # Write first line
            self.lcd.cursor_pos = (0, 0)
            self.lcd.write_string(line1)

            # Write second line
            self.lcd.cursor_pos = (1, 0)
            self.lcd.write_string(line2)

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
                await self.update_display(
                    f"B: {b_field_formatted}", f"Acq Time: {time_str}"
                )

            elif self.current_state == State.FFT:
                if not self.freq or not self.last_voltage:
                    await self.update_display("FFT View", "No data yet")
                peak_freq, peak_mag = self.freq, self.last_voltage
                await self.update_display(
                    f"Peak: {peak_freq:.1f}Hz", f"Mag: {peak_mag:.6f}V"
                )

            elif self.current_state == State.ADJUSTING:
                time_str = self.format_time(self.data_acquisition_time)
                await self.update_display("ADJUSTING", f"Acq Time: {time_str}")

            else:
                await self.update_display(
                    "Unknown State", f"State: {self.current_state}"
                )

        except Exception as e:
            logger.error(f"Error updating display with state: {e}")

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

    async def run(self) -> None:
        """Main run loop"""
        tasks = []

        try:
            # Initialize display
            await self.initialize_display()

            # Start button polling task
            button_task = asyncio.create_task(self.poll_buttons())
            tasks.append(button_task)

            # Start potentiometer polling task
            pot_task = asyncio.create_task(self.poll_potentiometer())
            tasks.append(pot_task)

            # Start data processing task
            data_task = asyncio.create_task(self.process_data())
            tasks.append(data_task)

            # Initial display update
            await self.update_display("Magnetometer", "Ready")
            await asyncio.sleep(1)
            await self.update_display_with_state()

            # Wait for tasks to complete (they shouldn't normally)
            await asyncio.gather(*tasks)

        except asyncio.CancelledError:
            logger.info("LCD controller main task cancelled")
        except Exception as e:
            logger.error(f"LCD controller error: {e}")
        finally:
            # Cancel all running tasks
            for task in tasks:
                if task and not task.done():
                    task.cancel()

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
            self.GPIO.cleanup()
        except Exception as e:
            logger.error(f"Error during GPIO cleanup: {e}")

        logger.info("Cleanup complete")
