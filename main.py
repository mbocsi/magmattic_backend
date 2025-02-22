import asyncio
import logging

from adc import ADCController, ADCInterface, NopADC
from front import FrontInterface, WSServer

logger = logging.getLogger(__name__)


class App:
    def __init__(
        self,
        front: FrontInterface,
        adc: ADCInterface,
        data_queue: asyncio.Queue,
        control_queue: asyncio.Queue,
    ) -> None:
        self.front = front
        self.adc = adc
        self.data_queue = data_queue
        self.control_queue = control_queue

    async def messageBroker(self) -> None:
        while True:
            data = await self.data_queue.get()
            await self.front.getDataQueue().put(data)
            # Put other data subscribers here

            # Also process control data maybe

    async def controlBroker(self) -> None:
        while True:
            data = await self.control_queue.get()
            logger.info(data)
            # Put other data subscribers here

            # Also process control data maybe

    async def run(self) -> None:
        await asyncio.gather(
            self.front.run(), self.adc.run(), self.messageBroker(), self.controlBroker()
        )


if __name__ == "__main__":
    # Logging settings
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)-35s %(message)s",
    )

    # Initialize queues
    control_queue = asyncio.Queue()
    data_queue = asyncio.Queue()

    # Initialize app components
    front = WSServer(
        asyncio.Queue(), control_queue, host="0.0.0.0", port=44444
    )  # Accept connections from all addresses
    adc = NopADC(data_queue)
    # adc = ADCController(data_queue, addr=0, pin="D0")

    # Initialize the app and run
    app = App(front, adc, data_queue, control_queue)  # Inject dependencies
    logger.info("starting app")
    asyncio.run(app.run())
