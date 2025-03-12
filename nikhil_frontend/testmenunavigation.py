import asyncio
import logging
import json
import math
import sys
import os
import random
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nikhil_frontend import LCDController

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)-35s %(message)s",
)

logger = logging.getLogger(__name__)

async def generate_test_data(q_data: asyncio.Queue):
    """Generate simulated voltage and FFT data for testing"""
    angle = 0
    try:
        while True:
            # Generate voltage data (sine wave with noise)
            angle = (angle + 0.1) % (2 * math.pi)
            voltage = math.sin(angle) + random.uniform(-0.1, 0.1)
            await q_data.put({"type": "voltage", "val": [voltage]})

            # Generate FFT data (multiple frequency components)
            # Primary peak at 50Hz
            primary_peak = [50.0, abs(voltage) * 0.8]
            # Secondary peak at 100Hz
            secondary_peak = [100.0, abs(voltage) * 0.5]
            # Tertiary peak at 150Hz
            tertiary_peak = [150.0, abs(voltage) * 0.3]
            # Some noise peaks
            noise_peaks = [
                [25.0, random.uniform(0.05, 0.1)],
                [75.0, random.uniform(0.05, 0.1)],
                [125.0, random.uniform(0.05, 0.1)]
            ]
            
            # Combine all peaks
            fft_data = [primary_peak, secondary_peak, tertiary_peak] + noise_peaks
            
            await q_data.put({"type": "fft", "val": fft_data})
            
            await asyncio.sleep(0.1)  # Update every 100ms

    except asyncio.CancelledError:
        pass

async def main():
    # Initialize queues for testing
    q_data = asyncio.Queue()
    q_control = asyncio.Queue()
    
    # Create LCD controller
    lcd = LCDController(q_data, q_control)
    
    # Start data generation in background
    data_task = asyncio.create_task(generate_test_data(q_data))
    
    # Run the controller
    try:
        logger.info("Starting LCD controller test")
        logger.info("Use UP/DOWN to navigate, SELECT to choose, BACK to cycle views")
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
        # Ensure cleanup is called
        await lcd.cleanup()
        logger.info("Test complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest stopped by user")
