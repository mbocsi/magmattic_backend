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

pot_value = 341  # Middle position by default
simulate_button_presses = True
button_press_interval = 5  # seconds

async def generate_test_data(q_data: asyncio.Queue):
    """Generate simulated voltage and FFT data for testing"""
    angle = 0
    last_button_time = time.time()
    
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
            
            # Simulate button presses if enabled
            if simulate_button_presses and time.time() - last_button_time > button_press_interval:
                if random.random() < 0.3:  # 30% chance to press a button
                    button = random.choice(["mode", "power"])
                    logger.info(f"Simulating {button} button press")
                    if lcd.button_states:  # Ensure LCD is initialized
                        if button == "mode":
                            await lcd.handle_button_press(17)  # BUTTON_MODE
                        else:
                            await lcd.handle_button_press(22)  # BUTTON_POWER
                    last_button_time = time.time()
            
            await asyncio.sleep(0.1)  # Update every 100ms

    except asyncio.CancelledError:
        pass

async def mock_read_potentiometer(channel):
    global pot_value
    
    # Simulate user adjusting the potentiometer based on time patterns
    current_time = time.time()
    sequence_time = current_time % 60
    
    if 5 <= sequence_time < 15:
        # Gradually increase (0.1s to 10s)
        target = int(min(1023, (sequence_time - 5) * 100))
        pot_value += (target - pot_value) // 5
        
    elif 20 <= sequence_time < 30:
        # Gradually decrease (10s to 0.1s)
        target = int(max(0, 1023 - (sequence_time - 20) * 100))
        pot_value += (target - pot_value) // 5
    
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
    
    # Run the controller
    try:
        logger.info("Starting LCD controller test")
        logger.info("B1: Toggle between B-field and FFT views")
        logger.info("B2: Toggle display power on/off")
        logger.info("POT1: Simulated adjustments to data acquisition time")
        
        # Run the LCD controller
        lcd_task = asyncio.create_task(lcd.run())
        
        # Run for a set time or until interrupted
        await asyncio.sleep(300)  # Run for 5 minutes
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        # Cancel all tasks
        for task in [data_task, control_task]:
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
