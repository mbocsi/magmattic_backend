import asyncio
from front import FrontInterface, WSServer
from adc import ADCController, ADCInterface, NopADC
import logging

logger = logging.getLogger(__name__)

class App:
    def __init__(self, front : FrontInterface, adc : ADCInterface) -> None:
        self.gui = front
        self.adc = adc
    
    async def run(self) -> None:
       await asyncio.gather(*(self.gui.run(), self.adc.run()))

if __name__ == "__main__":
    # Logging settings
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-7s %(name)-35s %(message)s')

    # Initialize queues
    q_data = asyncio.Queue()
    q_control = asyncio.Queue()

    # Initialize app components
    front = WSServer(q_data, q_control, host="localhost", port=8888)
    adc = NopADC()
    # adc = ADCController(q_data, addr=0, pin='D0')

    # Initialize the app and run
    app = App(front, adc) # Inject dependencies
    logger.info("starting app")
    asyncio.run(app.run())