import asyncio
import json
import math
import logging
import sys
import os

sys.path.append('/home/Documents/magmattic_backend/nikhil_frontend')

from nikhil_frontend.lcdcontroller import LCDController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)-35s %(message)s",
)

async def generate_test_data(q_data: asyncio.Queue):
    """Generate simulated voltage and FFT data"""
    angle = 0
    try:
        while True:
            # Generate voltage data (sine wave)
            angle = (angle + 0.1) % (2 * math.pi)
            voltage = math.sin(angle)
            await q_data.put({"type": "voltage", "val": [voltage]})

            # Generate FFT data (simulated frequency peaks)
            fft_data = [
                [10.0, 0.05],
                [20.0, 0.02],
                [50.0, 0.8],  # Main peak
                [100.0, 0.1],
                [150.0, 0.03]
            ]
            await q_data.put({"type": "fft", "val": fft_data})

            # Wait before sending next update
            await asyncio.sleep(0.2)
    except asyncio.CancelledError:
        pass

async def main():
    # Initialize queues
    q_data = asyncio.Queue()
    q_control = asyncio.Queue()

    # Create and start LCD controller
    lcd = LCDController(q_data, q_control)
    lcd_task = asyncio.create_task(lcd.run())
    
    # Start data generation
    data_task = asyncio.create_task(generate_test_data(q_data))
    
    print("LCD Menu Test Running")
    print("---------------------")
    print("- Press UP/DOWN to navigate menu")
    print("- Press SELECT to enter menu/select option")
    print("- Press BACK to return to main display")
    print("- Press Ctrl+C to exit")

    try:
        # Run until interrupted
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nTest stopped by user")
    finally:
        # Cleanup
        data_task.cancel()
        lcd_task.cancel()
        await asyncio.gather(data_task, lcd_task, return_exceptions=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest stopped by user")
