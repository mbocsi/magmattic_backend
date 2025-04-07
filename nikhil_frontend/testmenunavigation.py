import asyncio
import logging
import random
import math
import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nikhil_frontend import LCDController
import RPi.GPIO as GPIO

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)-35s %(message)s",
)

logger = logging.getLogger(__name__)

# Global variables for potentiometer simulation
pot_value = 341  # Middle position by default

async def generate_test_data(q_data: asyncio.Queue):
    """Generate simulated voltage and FFT data for testing"""
    angle = 0
    
    try:
        while True:
            # Generate voltage data (sine wave with noise)
            angle = (angle + 0.1) % (2 * math.pi)
            voltage = math.sin(angle) + random.uniform(-0.1, 0.1)
            
            # Send voltage data
            await q_data.put({
                "topic": "voltage/data", 
                "payload": [voltage]
            })

            # Generate FFT data
            # Primary peak at 50Hz
            primary_peak = [50.0, abs(voltage) * 0.8]
            # Secondary peak at 100Hz
            secondary_peak = [100.0, abs(voltage) * 0.5]
            # Some noise peaks
            noise_peaks = [
                [25.0, random.uniform(0.05, 0.1)],
                [75.0, random.uniform(0.05, 0.1)]
            ]
            
            # Combine all peaks
            fft_data = [primary_peak, secondary_peak] + noise_peaks
            
            # Send FFT data
            await q_data.put({
                "topic": "fft/data", 
                "payload": fft_data
            })
            
            # Sleep rate controls data generation speed
            await asyncio.sleep(0.2)  # 5Hz update rate

    except asyncio.CancelledError:
        logger.info("Data generation task cancelled")
    except Exception as e:
        logger.error(f"Error in data generation: {e}")

# Mock the potentiometer reading for testing
async def mock_read_potentiometer(channel):
    """Simulate reading from a potentiometer"""
    global pot_value
    return pot_value

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
        lcd = LCDController(q_data, q_control)
        
        # Replace the potentiometer reading with our mock function
        lcd.read_potentiometer = mock_read_potentiometer
        
        # Start data generation
        data_task = asyncio.create_task(generate_test_data(q_data))
        tasks.append(data_task)
        
        # Start control message handler
        control_task = asyncio.create_task(control_message_handler(q_control))
        tasks.append(control_task)
        
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
        # Clean up any existing GPIO setup
        try:
            GPIO.cleanup()
        except:
            pass
            
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
