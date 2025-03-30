import asyncio
import logging
import random
import math
import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nikhil_frontend import LCDController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)-35s %(message)s",
)

logger = logging.getLogger(__name__)

pot_value = 341  # Middle position by default (corresponds to ~1s acquisition time)
simulate_button_presses = False  # Turn off auto button press simulation

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
            
            # No more automatic button simulation
            
            await asyncio.sleep(0.1)  # Update every 100ms

    except asyncio.CancelledError:
        pass

async def mock_read_potentiometer(channel):
    global pot_value
    # Simply return the current pot value without automatic adjustments
    return pot_value

async def control_message_handler(q_control: asyncio.Queue):
    """Handle control messages sent from LCD controller"""
    while True:
        try:
            control_msg = await q_control.get()
            logger.info(f"Control message: {control_msg}")
        except Exception as e:
            logger.error(f"Error in control message handler: {e}")
            await asyncio.sleep(1)

async def handle_user_input():
    """Handle keyboard input from the user to control the simulation"""
    global pot_value
    
    print("\nInteractive controls:")
    print("  m - Simulate mode button press")
    print("  p - Simulate power button press")
    print("  + - Increase data acquisition time")
    print("  - - Decrease data acquisition time")
    print("  q - Quit the test")
    
    while True:
        try:
            # Use standard input in a non-blocking way
            if not sys.stdin.isatty():
                await asyncio.sleep(1)
                continue
                
            cmd = await asyncio.to_thread(sys.stdin.readline)
            
            if cmd.strip() == 'm':
                logger.info("User requested MODE button press")
                if lcd.button_states:
                    await lcd.handle_button_press(17)  # BUTTON_MODE
            
            elif cmd.strip() == 'p':
                logger.info("User requested POWER button press")
                if lcd.button_states:
                    await lcd.handle_button_press(22)  # BUTTON_POWER
            
            elif cmd.strip() == '+':
                # Increase acquisition time by increasing pot value
                pot_value = min(1023, pot_value + 50)
                acq_time = 0.1 * (10 ** (pot_value / 341.0))
                logger.info(f"User increased pot value to {pot_value} (approx. {acq_time:.2f}s)")
            
            elif cmd.strip() == '-':
                # Decrease acquisition time by decreasing pot value
                pot_value = max(0, pot_value - 50)
                acq_time = 0.1 * (10 ** (pot_value / 341.0))
                logger.info(f"User decreased pot value to {pot_value} (approx. {acq_time:.2f}s)")
            
            elif cmd.strip() == 'q':
                logger.info("User requested to quit")
                return
                
            await asyncio.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Error in user input handler: {e}")
            await asyncio.sleep(1)

async def main():
    global lcd
    
    # Initialize queues for testing
    q_data = asyncio.Queue()
    q_control = asyncio.Queue()
    
    # Create LCD controller
    lcd = LCDController(q_data, q_control)
    
    # Replace the potentiometer reading with our mock function
    lcd.read_potentiometer = mock_read_potentiometer
    
    # Start tasks
    data_task = asyncio.create_task(generate_test_data(q_data))
    control_task = asyncio.create_task(control_message_handler(q_control))
    user_input_task = asyncio.create_task(handle_user_input())
    
    # Run the controller
    try:
        logger.info("Starting LCD controller test")
        logger.info("Manual control only - use keyboard inputs to control the test")
        
        # Run the LCD controller
        lcd_task = asyncio.create_task(lcd.run())
        
        # Wait until user quits or timeout
        done, pending = await asyncio.wait(
            [user_input_task, lcd_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        # Cancel all tasks
        for task in [data_task, control_task, user_input_task]:
            if task and not task.done():
                task.cancel()
                
        # Ensure cleanup is called
        await lcd.cleanup()
        logger.info("Test complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest stopped by user")
