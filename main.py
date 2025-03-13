import asyncio
import logging
from collections import defaultdict

from adc import ADCComponent, VirtualADCComponent
from ws import WebSocketComponent
from motor import MotorComponent, VirtualMotorComponent
from lcd import LCDComponent, VirtualLCDComponent
from app_interface import AppComponent

logger = logging.getLogger(__name__)


class App:
    def __init__(
        self,
        *deps: AppComponent,
        pub_queue: asyncio.Queue,
    ) -> None:
        self.deps = deps
        self.pub_queue = pub_queue
        self.subs = defaultdict(lambda: [])

    def registerSub(self, keys: list[str] | str, sub_queue: asyncio.Queue) -> None:
        for key in keys:
            self.subs[key].append(sub_queue)

    async def broker(self) -> None:
        while True:
            data = await self.pub_queue.get()
            for queue in self.subs.get(data["topic"], []):
                await queue.put(data)

    async def run(self) -> None:
        await asyncio.gather(*[dep.run() for dep in self.deps], self.broker())


if __name__ == "__main__":
    # === Logging settings ===
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)-35s %(message)s",
    )

    # === Initialize App queues ===
    app_pub_queue = asyncio.Queue()

    # === Initialize WS server ===
    ws_sub_queue = asyncio.Queue()
    ws = WebSocketComponent(
        pub_queue=app_pub_queue, sub_queue=ws_sub_queue, host="0.0.0.0", port=44444
    )

    # === Initialize ADC controller ===
    adc_sub_queue = asyncio.Queue()
    # adc = ADCComponent(pub_queue=app_pub_queue, sub_queue=adc_sub_queue)
    adc = VirtualADCComponent(pub_queue=app_pub_queue, sub_queue=adc_sub_queue)

    # === Initialize Motor Controller ===
    motor_sub_queue = asyncio.Queue()
    # motor = MotorComponent(data_queue, motor_control_queue)
    motor = VirtualMotorComponent(pub_queue=app_pub_queue, sub_queue=motor_sub_queue)

    # === Initialize LCD Component ===
    lcd_sub_queue = asyncio.Queue()
    # lcd = LCDComponent(lcd_data_queue)
    lcd = VirtualLCDComponent(sub_queue=lcd_sub_queue)

    # === Initialize the app ===
    app = App(ws, adc, motor, lcd, pub_queue=app_pub_queue)  # Inject dependencies

    # === Add queue subscriptions ===
    app.registerSub(["adc/command"], adc_sub_queue)
    app.registerSub(["voltage/data", "fft/data", "motor/data"], ws_sub_queue)
    app.registerSub(["motor/command"], motor_sub_queue)
    app.registerSub(["fft/data"], lcd_sub_queue)

    logger.info("starting app")
    asyncio.run(app.run())
