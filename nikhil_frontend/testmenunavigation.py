import asyncio
import logging
import random
import math
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nikhil_frontend import LCDController

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)-35s %(message)s",
)

logger = logging.getLogger(__name__)

# Simulated ADC channel for potentiometer reading
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

            # Generate FFT data (multiple frequency components)
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
            
            await asyncio.sleep(0.1)  # Update every 100ms

    except asyncio.CancelledError:
        pass

# Mock function to simulate reading potentiometer
async def mock_read_potentiometer(channel):
    global pot_value
    # Occasionally simulate user adjusting the potentiometer
    if random.random() < 0.01:  # 1% chance each cycle
        adjustment = random.choice([-30, -15, 15, 30])  # Random adjustment
        pot_value = max(0, min(1023, pot_value + adjustment))  # Keep in range
        logger.info(f"Simulated potentiometer adjustment to {pot_value}")
    return pot_value

async def main():
    # Initialize queues for testing
    q_data = asyncio.Queue()
    q_control = asyncio.Queue()
    
    # Create LCD controller
    lcd = LCDController(q_data, q_control)
    
    # Replace the potentiometer reading with our mock function
    lcd.read_potentiometer = mock_read_potentiometer
    
    # Start data generation in background
    data_task = asyncio.create_task(generate_test_data(q_data))
    
    # Monitor control messages
    async def monitor_control():
        while True:
            control_msg = await q_control.get()
            logger.info(f"Control message sent: {control_msg}")
    
    control_task = asyncio.create_task(monitor_control())
    
    # Run the controller
    try:
        logger.info("Starting LCD controller test")
        logger.info("B1: Toggle between B-field and FFT views")
        logger.info("B2: Toggle display power on/off")
        logger.info("POT1: Simulated random adjustments to data acquisition time")
        logger.info("Press Ctrl+C to exit")
        
        # Run the LCD controller
        lcd_task = asyncio.create_task(lcd.run())
        
        # Keep running until interrupted
        await asyncio.gather(lcd_task)
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        # Cancel all tasks
        data_task.cancel()
        control_task.cancel()
        # Ensure cleanup is called
        await lcd.cleanup()
        logger.info("Test complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest stopped by user")
