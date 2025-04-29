import asyncio
import logging
import random
import math
import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from pui import PUIComponent
import RPi.GPIO as GPIO

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)-35s %(message)s",
)

logger = logging.getLogger(__name__)

# Global variables for potentiometer simulation
pot_value = 341  # Middle position by default
last_pot_value = 341  # Track changes

# Set GPIO mode once globally
try:
    GPIO.setmode(GPIO.BCM)
except:
    pass

async def generate_test_data(q_data: asyncio.Queue):
    """Generate simulated voltage and FFT data for testing"""
    angle = 0
    
    try:
        while True:
            # Generate voltage data (sine wave with noise)
            angle = (angle + 0.1) % (2 * math.pi)
            voltage = math.sin(angle) + random.uniform(-0.1, 0.1)
            
            # Calculate simulated B-field
            b_field_x = math.cos(angle) * random.uniform(0.5, 1.5) * 0.000025  # Random B-field strength
            b_field_y = math.sin(angle) * random.uniform(0.5, 1.5) * 0.000025
            b_field = [b_field_x, b_field_y]  # Vector form
            
            # Send signal data that matches the expected format in PUIComponent
            await q_data.put({
                "topic": "signal/data", 
                "payload": {
                    "freq": 50.0,  # Simulated peak frequency in Hz
                    "mag": abs(voltage),  # Signal magnitude
                    "phase": angle,  # Signal phase in radians
                    "ampl": abs(voltage),  # Signal amplitude
                    "bfield": b_field  # B-field vector
                }
            })
            
            # Generate FFT data (optional, could add later if needed)
            # Sleep rate controls data generation speed
            await asyncio.sleep(0.2)  # 5Hz update rate

    except asyncio.CancelledError:
        logger.info("Data generation task cancelled")
    except Exception as e:
        logger.error(f"Error in data generation: {e}")

async def mock_read_potentiometer(channel):
    """Simulate reading from a potentiometer"""
    global pot_value
    # Return value as voltage (0-5V) to match ADC output
    return pot_value * 5.0 / 1023.0

async def control_message_handler(q_control: asyncio.Queue):
    """Handle control messages sent from LCD controller"""
    while True:
        try:
            control_msg = await q_control.get()
            logger.info(f"Control message: {control_msg}")
            q_control.task_done()
        except asyncio.CancelledError:
            logger.info("Control message handler cancelled")
            break
        except Exception as e:
            logger.error(f"Error in control message handler: {e}")
            await asyncio.sleep(1)

async def simulate_pot_change():
    """Periodically check if global pot value has changed and update LCD controller"""
    global pot_value, last_pot_value
    
    try:
        while True:
            # If pot value has changed significantly, log it
            if abs(pot_value - last_pot_value) > 10:
                logger.info(f"Potentiometer changed from {last_pot_value} to {pot_value}")
                last_pot_value = pot_value
                
            await asyncio.sleep(0.1)
            
    except asyncio.CancelledError:
        logger.info("Pot change simulator cancelled")
    except Exception as e:
        logger.error(f"Error in pot change simulator: {e}")

async def handle_user_input():
    """Handle user keyboard input for testing"""
    global pot_value
    
    print("\nManual Test Controls:")
    print("  m - Simulate mode button press")
    print("  p - Simulate power button press")
    print("  + - Increase data acquisition time")
    print("  - - Decrease data acquisition time")
    print("  q - Quit test")
    print("\nEnter command: ", end='', flush=True)
    
    while True:
        # Non-blocking input check
        if sys.stdin in asyncio.get_event_loop()._ready:
            cmd = sys.stdin.readline().strip().lower()
            
            if cmd == 'q':
                logger.info("User requested exit")
                return True
                
            elif cmd == 'm':
                logger.info("Simulating mode button press - manually triggering")
                # Directly call the handler instead of through GPIO
                if hasattr(lcd, 'handle_button_press'):
                    await lcd.handle_button_press(17)  # BUTTON_MODE
                
            elif cmd == 'p':
                logger.info("Simulating power button press - manually triggering")
                if hasattr(lcd, 'handle_button_press'):
                    await lcd.handle_button_press(22)  # BUTTON_POWER
                
            elif cmd == '+':
                # Increase DAT (move potentiometer value up)
                pot_value = min(1023, pot_value + 50)
                logger.info(f"Increased DAT potentiometer to {pot_value}")
                
            elif cmd == '-':
                # Decrease DAT (move potentiometer value down)
                pot_value = max(0, pot_value - 50)
                logger.info(f"Decreased DAT potentiometer to {pot_value}")
                
            print("\nEnter command: ", end='', flush=True)
            
        await asyncio.sleep(0.1)
    
    return False

async def main():
    global lcd
    
    # Initialize queues for testing
    q_data = asyncio.Queue()
    q_control = asyncio.Queue()
    
    # Tasks list for proper cleanup
    tasks = []
    
    try:
        # Create LCD controller
        lcd = PUIComponent(q_data, q_control)
        
        # Monkey patch the ADC read method
        # This is required because the PUIComponent uses ADC.getADC in poll_potentiometer
        from piplates import ADCplate as ADC
        original_getADC = ADC.getADC
        
        def mock_getADC(addr, chan):
            global pot_value
            if addr == 0 and chan == 0:  # This is the POT_DAT channel
                return pot_value * 5.0 / 1023.0
            return original_getADC(addr, chan)
        
        # Apply the monkey patch
        ADC.getADC = mock_getADC
        
        # Start data generation
        data_task = asyncio.create_task(generate_test_data(q_data))
        tasks.append(data_task)
        
        # Start control message handler
        control_task = asyncio.create_task(control_message_handler(q_control))
        tasks.append(control_task)
        
        # Start potentiometer change simulator
        pot_task = asyncio.create_task(simulate_pot_change())
        tasks.append(pot_task)
        
        # User input handling
        user_task = asyncio.create_task(handle_user_input())
        tasks.append(user_task)
        
        # Run the LCD controller
        logger.info("Starting LCD controller test")
        logger.info("Use keyboard for manual control:")
        logger.info("  m - Toggle between B-field and FFT views")
        logger.info("  p - Toggle display power on/off")
        logger.info("  +/- - Adjust data acquisition time")
        logger.info("  q - Quit the test")
        
        lcd_task = asyncio.create_task(lcd.run())
        tasks.append(lcd_task)
        
        # Wait until user requests exit
        await user_task
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        logger.info("Cleaning up...")
        
        # Restore original ADC function if we patched it
        if 'original_getADC' in locals():
            ADC.getADC = original_getADC
        
        # Cancel all tasks
        for task in tasks:
            if task and not task.done():
                task.cancel()
                
        # Wait for tasks to complete
        if tasks:
            try:
                await asyncio.wait(tasks, timeout=1.0)
            except Exception as e:
                logger.error(f"Error during task cleanup: {e}")
                
        # Ensure LCD cleanup is called
        if 'lcd' in globals() and lcd:
            try:
                await lcd.cleanup()
            except Exception as e:
                logger.error(f"Error during LCD cleanup: {e}")
            
        logger.info("Test complete")

if __name__ == "__main__":
    try:
        # Use asyncio.run to ensure proper cleanup of event loop
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest stopped by user")
    finally:
        # Final GPIO cleanup
        try:
            GPIO.cleanup()
        except:
            pass
