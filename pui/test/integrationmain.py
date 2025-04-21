import asyncio
import logging
from collections import defaultdict

# Import your components
from adc import VirtualADCComponent  # Use virtual for testing
from nikhil_frontend import LCDController
from app_interface import AppComponent

logger = logging.getLogger(__name__)

class App:
    def __init__(self, *deps: AppComponent, pub_queue: asyncio.Queue) -> None:
        self.deps = deps
        self.pub_queue = pub_queue
        self.subs = defaultdict(lambda: [])
    
    def registerSub(self, topics: list[str], sub_queue: asyncio.Queue) -> None:
        """Register a subscriber to topics"""
        for topic in topics:
            if sub_queue not in self.subs[topic]:
                self.subs[topic].append(sub_queue)
            else:
                logger.warning(f"Queue already subscribed to {topic}")
    
    async def broker(self) -> None:
        """Broker messages between components"""
        while True:
            try:
                data = await self.pub_queue.get()
                
                # Handle subscriptions
                if data["topic"] == "subscribe":
                    self.registerSub(data["payload"]["topics"], data["payload"]["sub_queue"])
                    continue
                
                # Forward messages to subscribers
                for queue in self.subs.get(data["topic"], []):
                    queue.put_nowait(data)
                    
            except Exception as e:
                logger.error(f"Error in broker: {e}")
    
    async def run(self) -> None:
        """Run all components"""
        await asyncio.gather(*[dep.run() for dep in self.deps], self.broker())

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)-35s %(message)s",
    )

    # Initialize queues
    app_pub_queue = asyncio.Queue()
    
    # Initialize components
    lcd_sub_queue = asyncio.Queue()
    lcd = LCDController(q_data=lcd_sub_queue, q_control=app_pub_queue)
    
    # Setup Virtual ADC for testing
    adc_sub_queue = asyncio.Queue()
    adc = VirtualADCComponent(pub_queue=app_pub_queue, sub_queue=adc_sub_queue)
    
    # Initialize app
    components = [lcd, adc]
    app = App(*components, pub_queue=app_pub_queue)
    
    # Register subscriptions
    app.registerSub(["voltage/data", "fft/data"], lcd_sub_queue)
    app.registerSub(["adc/command"], adc_sub_queue)
    
    # Start the app
    logger.info("Starting magnetometer app")
    asyncio.run(app.run())
