import asyncio
import logging
import json
from collections import defaultdict

from adc import ADCController, NopADC
from ws import WebSocketServer
from app_interface import AppInterface

logger = logging.getLogger(__name__)


class App:
    def __init__(
        self,
        *deps: AppInterface,
        data_queue: asyncio.Queue,
        control_queue: asyncio.Queue,
    ) -> None:
        self.deps = deps
        self.data_queue = data_queue
        self.control_queue = control_queue
        self.data_subs = defaultdict(lambda: [])
        self.control_subs = defaultdict(lambda: [])

    def registerDataSub(self, keys: list[str], queue: asyncio.Queue) -> None:
        for key in keys:
            self.data_subs[key].append(queue)

    def registerControlSub(self, keys: list[str], queue: asyncio.Queue) -> None:
        for key in keys:
            self.control_subs[key].append(queue)

    async def dataBroker(self) -> None:
        while True:
            data = await self.data_queue.get()
            for queue in self.data_subs.get(data.get("type"), []):
                await queue.put(data)

    async def controlBroker(self) -> None:
        while True:
            data = await self.control_queue.get()
            data = json.loads(data)
            for queue in self.control_subs.get(data.get("type"), []):
                await queue.put(data)

    async def run(self) -> None:
        await asyncio.gather(
            *[dep.run() for dep in self.deps], self.dataBroker(), self.controlBroker()
        )


if __name__ == "__main__":
    # === Logging settings ===
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)-35s %(message)s",
    )

    # === Initialize App queues ===
    control_queue = asyncio.Queue()
    data_queue = asyncio.Queue()

    # === Initialize WS server ===
    ws_data_queue = asyncio.Queue()
    ws_server = WebSocketServer(
        ws_data_queue, control_queue, host="0.0.0.0", port=44444
    )

    # === Initialize ADC controller ===
    adc_control_queue = asyncio.Queue()
    adc = NopADC(data_queue, adc_control_queue)
    # adc = ADCController(data_queue, adc_control_queue, addr=0, pin="D0")

    # === Initialize the app ===
    app = App(
        ws_server, adc, data_queue=data_queue, control_queue=control_queue
    )  # Inject dependencies

    # === Add queue subscriptions ===
    app.registerControlSub(["adc"], adc_control_queue)
    app.registerDataSub(["voltage", "fft"], ws_data_queue)

    logger.info("starting app")
    asyncio.run(app.run())
