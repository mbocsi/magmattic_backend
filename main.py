import asyncio
import logging
from collections import defaultdict
from typeguard import check_type, TypeCheckError


from calculation import CalculationComponent
from adc import ADCComponent, VirtualADCComponent
from app_interface import AppComponent

# from lcd import LCDComponent, VirtualLCDComponent  # Deprecated: don't use
from motor import MotorComponent, VirtualMotorComponent

# from nikhil_frontend import LCDController  # Please rename this package
from ws import WebSocketComponent
from type_defs import ADCStatus, CalculationStatus, Message, MotorStatus
import time

logger = logging.getLogger(__name__)


class App:
    def __init__(
        self,
        *deps: AppComponent,
        pub_queue: asyncio.Queue,
    ) -> None:
        self.deps = deps
        self.pub_queue = pub_queue
        self.subs: dict[str, list[asyncio.Queue]] = defaultdict(lambda: [])
        self.adc_status: ADCStatus | None = None
        self.calculation_status: CalculationStatus | None = None
        self.motor_status: MotorStatus | None = None

    def registerSub(self, topics: list[str] | str, sub_queue: asyncio.Queue) -> None:
        for topic in topics:
            if sub_queue not in self.subs[topic]:
                self.subs[topic].append(sub_queue)
                if self.adc_status is not None and topic == "adc/status":
                    sub_queue.put_nowait(
                        {"topic": "adc/status", "payload": self.adc_status}
                    )
                elif (
                    self.calculation_status is not None
                    and topic == "calculation/status"
                ):
                    sub_queue.put_nowait(
                        {
                            "topic": "calculation/status",
                            "payload": self.calculation_status,
                        }
                    )
                elif self.motor_status is not None and topic == "motor/status":
                    sub_queue.put_nowait(
                        {
                            "topic": "calculation/status",
                            "payload": self.motor_status,
                        }
                    )

            else:
                logger.warning(
                    f"This queue is already subscribed to {topic}: {sub_queue}"
                )
        logger.info(f"added subscriber to topics: {topics}")

    def deleteSub(self, sub_queue: asyncio.Queue):
        deletedTopics = []
        for topic in self.subs.keys():
            if sub_queue in self.subs[topic]:
                deletedTopics.append(topic)
                self.subs[topic].remove(sub_queue)
        logger.info(f"Removed subscriber from topics: {deletedTopics}")

    async def broker(self) -> None:
        while True:
            try:
                data = await self.pub_queue.get()
                check_type(data, Message)

                match data["topic"]:
                    case "subscribe":
                        self.registerSub(
                            data["payload"]["topics"], data["payload"]["sub_queue"]
                        )
                    case "unsubscribe":
                        self.deleteSub(data["payload"])
                    case "adc/status":
                        check_type(data["payload"], ADCStatus)
                        self.adc_status = data["payload"]
                        for queue in self.subs.get(data["topic"], []):
                            queue.put_nowait(data)
                    case "calculation/status":
                        check_type(data["payload"], CalculationStatus)
                        self.calculation_status = data["payload"]
                        for queue in self.subs.get(data["topic"], []):
                            queue.put_nowait(data)
                    case "motor/status":
                        check_type(data["payload"], MotorStatus)
                        self.motor_status = data["payload"]
                        for queue in self.subs.get(data["topic"], []):
                            queue.put_nowait(data)
                    case _:
                        for queue in self.subs.get(data["topic"], []):
                            queue.put_nowait(data)

            except TypeCheckError as e:
                logger.warning(f"Invalid message format: {data} -> {e}")
            except Exception as e:
                logger.error(f"There was an unexpected error in broker: {e}")

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

    # === Initialize Motor Controller ===
    motor_sub_queue = asyncio.Queue()
    # motor = MotorComponent(data_queue, motor_control_queue)
    motor = VirtualMotorComponent(
        pub_queue=app_pub_queue, sub_queue=motor_sub_queue, init_speed=5
    )

    # === Initialize ADC controller (PiPlate or Virtual ADC Only! Comment out if using ESP32) ===
    adc_sub_queue = asyncio.Queue()
    # adc = ADCComponent(pub_queue=app_pub_queue, sub_queue=adc_sub_queue)
    adc = VirtualADCComponent(
        pub_queue=app_pub_queue, sub_queue=adc_sub_queue, motor_component=motor
    )

    # === Initialize LCD Component ===
    # lcd_sub_queue = asyncio.Queue()
    # lcd = LCDComponent(lcd_data_queue)
    # lcd = VirtualLCDComponent(sub_queue=lcd_sub_queue)

    # === Initialize Frontend ===
    # frontend_sub_queue = asyncio.Queue()
    # frontend = LCDController(frontend_sub_queue, app_pub_queue)

    calculation_sub_queue = asyncio.Queue()
    calculation = CalculationComponent(
        pub_queue=app_pub_queue,
        sub_queue=calculation_sub_queue,
        motor_component=motor,
        Nsig=1200,
        Ntot=1200,
    )

    # === Initialize the app ===
    components = [
        ws,
        calculation,
        motor,
        adc,
        # frontend,
    ]  # Add all components to this array
    app = App(*components, pub_queue=app_pub_queue)

    # === Add queue subscriptions ===
    app.registerSub(
        ["voltage/data", "calculation/command", "adc/status"],
        calculation_sub_queue,
    )

    # Uncomment this if using motor component
    app.registerSub(["motor/command"], motor_sub_queue)

    # Uncomment this if using lcd
    # app.registerSub(["fft/data"], lcd_sub_queue)

    # Only uncomment this if using PiPlate or Virtual ADC
    # app.registerSub(["adc/command"], adc_sub_queue)

    # Uncomment this if using Frontend
    # app.registerSub(["signal/data"], frontend_sub_queue)

    logger.info("starting app")
    asyncio.run(app.run())
