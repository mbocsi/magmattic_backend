import asyncio
import json
import math
import logging
from nikhil_front.lcd_controller import LCDController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)-35s %(message)s",
)

async def generate_test_data(q_data: asyncio.Queue):
    """Generate simulated voltage and FFT data"""
    angle = 0
    try:
        while True:
            # Generate voltage data
            angle = (angle + 0.1) % (2 * math.pi)
            voltage = math.sin(angle)
            await q_data.put(json.dumps({
                "type": "voltage",
                "val": [voltage]
            }))
            
            # Generate FFT data
            await q_data.put(json.dumps({
                "type": "fft",
                "val": [[50.0, abs(voltage)]]  # Simulated 50Hz peak
            }))
            
            await asyncio.sleep(0.1)  # Update every 100ms
            
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
    
    try:
        # Run for 30 seconds
        await asyncio.sleep(30)
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
