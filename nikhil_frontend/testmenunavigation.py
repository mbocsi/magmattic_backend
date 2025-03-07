import asyncio
import logging
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

async def main():
    # Initialize empty queues for testing
    q_data = asyncio.Queue()
    q_control = asyncio.Queue()
    
    # Create LCD controller
    lcd = LCDController(q_data, q_control)
    
    # Run the controller
    try:
        logger.info("Starting LCD controller test")
        await lcd.run()
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        # Ensure cleanup is called
        await lcd.cleanup()
        logger.info("Test complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest stopped by user")
