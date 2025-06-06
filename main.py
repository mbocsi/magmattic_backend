import asyncio
import logging
from collections import defaultdict
from typeguard import check_type, TypeCheckError
import argparse


from app_interface import AppComponent
from calculation import CalculationComponent
from adc import ADCComponent, VirtualADCComponent
from motor import MotorComponent, VirtualMotorComponent
from pui import PUIComponent
from ws import WebSocketComponent
from type_defs import ADCStatus, CalculationStatus, Message, MotorStatus

logger = logging.getLogger(__name__)


class App:
    def __init__(
        self,
        *deps: AppComponent,
        pub_queue: asyncio.Queue,
    ) -> None:
        """
        Main application orchestrator that wires components together and routes messages.

        Args:
            *deps: List of AppComponent instances to run.
            pub_queue (asyncio.Queue): Central queue where all components publish messages.
        """
        self.deps = deps
        self.pub_queue = pub_queue
        self.subs: dict[str, list[asyncio.Queue]] = defaultdict(lambda: [])
        self.adc_status: ADCStatus | None = None
        self.calculation_status: CalculationStatus | None = None
        self.motor_status: MotorStatus | None = None

    def registerSub(self, topics: list[str] | str, sub_queue: asyncio.Queue) -> None:
        """
        Registers a queue to receive messages published on specific topics.
        Automatically pushes latest status messages to the subscriber if available.

        Args:
            topics (list[str] | str): Topics to subscribe to.
            sub_queue (asyncio.Queue): Queue to forward matching messages to.
        """
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
                            "topic": "motor/status",
                            "payload": self.motor_status,
                        }
                    )

            else:
                logger.warning(
                    f"This queue is already subscribed to {topic}: {sub_queue}"
                )
        logger.info(f"added subscriber to topics: {topics}")

    def deleteSub(self, sub_queue: asyncio.Queue):
        """
        Removes a queue from all topic subscriptions.

        Args:
            sub_queue (asyncio.Queue): The queue to unsubscribe.
        """
        deletedTopics = []
        for topic in self.subs.keys():
            if sub_queue in self.subs[topic]:
                deletedTopics.append(topic)
                self.subs[topic].remove(sub_queue)
        logger.info(f"Removed subscriber from topics: {deletedTopics}")

    async def broker(self) -> None:
        """
        Central message broker that routes incoming messages from components
        to all queues subscribed to the corresponding topic.
        """
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
        """
        Starts all components concurrently along with the broker.
        """
        await asyncio.gather(*[dep.run() for dep in self.deps], self.broker())


if __name__ == "__main__":
    # === Command-line arguments ===
    parser = argparse.ArgumentParser(description="Start the Magmattic application.")
    parser.add_argument(
        "--dev", action="store_true", help="Run in local development mode"
    )
    parser.add_argument(
        "--adc-mode", choices=["none", "virtual", "piplate"], help="Specify ADC mode"
    )
    parser.add_argument(
        "--motor-mode", choices=["virtual", "physical"], help="Specify motor type"
    )
    parser.add_argument(
        "--pui-mode", choices=["enable", "disable"], help="Enable or disable PUI"
    )
    args = parser.parse_args()

    # === Logging settings ===
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)-35s %(message)s",
    )

    # === Resolve effective configuration ===
    motor_mode = args.motor_mode or ("virtual" if args.dev else "physical")
    adc_mode = args.adc_mode or ("virtual" if args.dev else "none")
    use_pui = (args.pui_mode == "enable") if args.pui_mode else not args.dev

    # === Initialize App queues ===
    app_pub_queue = asyncio.Queue()

    # === Initialize WS server ===
    ws_sub_queue = asyncio.Queue()
    ws = WebSocketComponent(
        pub_queue=app_pub_queue, sub_queue=ws_sub_queue, host="0.0.0.0", port=44444
    )

    # === Initialize Motor Controller ===
    motor_sub_queue = asyncio.Queue()
    if motor_mode == "virtual":
        motor = VirtualMotorComponent(
            pub_queue=app_pub_queue, sub_queue=motor_sub_queue, init_speed=5
        )
    else:
        motor = MotorComponent(
            pub_queue=app_pub_queue, sub_queue=motor_sub_queue, init_speed=5
        )
    logger.info(f"Initialized motor type: {type(motor).__name__}")

    # === Initialize ADC controller ===
    adc_sub_queue = asyncio.Queue()
    adc = None
    if adc_mode == "piplate":
        adc = ADCComponent(pub_queue=app_pub_queue, sub_queue=adc_sub_queue)
    elif adc_mode == "virtual":
        adc = VirtualADCComponent(
            pub_queue=app_pub_queue, sub_queue=adc_sub_queue, motor_component=motor
        )
    if adc:
        logger.info(f"Initialized ADC type: {type(adc).__name__}")

    # === Initialize PUI ===
    pui_sub_queue = asyncio.Queue()
    pui = None
    if use_pui:
        pui = PUIComponent(pui_sub_queue, app_pub_queue)

    # === Initialize Calculation Engine ===
    calculation_sub_queue = asyncio.Queue()
    calculation = CalculationComponent(
        pub_queue=app_pub_queue,
        sub_queue=calculation_sub_queue,
        motor_component=motor,
        Nsig=1200,
        Ntot=1200,
    )

    # === Register components ===
    components = [ws, calculation, motor]
    if adc:
        components.append(adc)
    if pui:
        components.append(pui)

    app = App(*components, pub_queue=app_pub_queue)

    # === Add subscriptions ===
    app.registerSub(
        ["voltage/data", "calculation/command", "adc/status"], calculation_sub_queue
    )
    app.registerSub(["motor/command"], motor_sub_queue)
    if adc:
        app.registerSub(["adc/command"], adc_sub_queue)
    if pui:
        app.registerSub(["signal/data"], pui_sub_queue)

    logger.info("starting app")
    asyncio.run(app.run())
