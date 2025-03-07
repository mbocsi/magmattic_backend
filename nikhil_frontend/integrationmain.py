import asyncio
import logging
import json
from collections import defaultdict

from adc import ADCController, NopADC
from nikhil_frontend import LCDController
from app_interface import AppComponent

logger = logging.getLogger(__name__)


class App:
    def __init__(
        self,
        *deps: AppComponent,
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
            if isinstance(data, str):
                # Handle string data (from old components)
                for queue in self.data_subs.get(json.loads(data).get("type", ""), []):
                    await queue.put(data)
            else:
                # Handle dict data (from new components)
                for queue in self.data_subs.get(data.get("type", ""), []):
                    await queue.put(data)

    async def controlBroker(self) -> None:
        while True:
            data = await self.control_queue.get()
            if isinstance(data, str):
                data = json.loads(data)
            for queue in self.control_subs.get(data.get("type", ""), []):
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

    # === Initialize LCD Controller ===
    lcd_data_queue = asyncio.Queue()
    lcd_controller = LCDController(lcd_data_queue, control_queue)

    # === Initialize ADC controller ===
    adc_control_queue = asyncio.Queue()
    # Uncomment this line to use real ADC:
    # adc = ADCController(data_queue, adc_control_queue, addr=0, pin="D0")
    # Use simulated ADC for testing:
    adc = NopADC(data_queue, adc_control_queue)

    # === Initialize the app ===
    app = App(
        lcd_controller, adc, data_queue=data_queue, control_queue=control_queue
    )  # Inject dependencies

    # === Add queue subscriptions ===
    app.registerControlSub(["adc"], adc_control_queue)
    app.registerDataSub(["voltage", "fft"], lcd_data_queue)

    logger.info("Starting magnetometer app with LCD display")
    asyncio.run(app.run())
