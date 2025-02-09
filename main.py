import asyncio
from frontInterface import FrontInterface
from socketFront import SocketFront
from adc import ADC
import logging

logger = logging.getLogger(__name__)

class App:
    def __init__(self, front : FrontInterface, adc : ADC) -> None:
        self.gui = front
        self.adc = adc
    
    async def run(self) -> None:
       await asyncio.gather(*(self.gui.run(), self.adc.run()))

if __name__ == "__main__":
    # Logging settings
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-7s %(name)-25s %(message)s')

    # Initialize queues
    q_data = asyncio.Queue()
    q_control = asyncio.Queue()

    # Initialize app components
    front = SocketFront(q_data, q_control, host="localhost", port=8888)
    adc = ADC(q_data, q_control)

    # Initialize the app and run
    app = App(front, adc) # Inject dependencies
    logger.info("starting app")
    asyncio.run(app.run())