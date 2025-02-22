import asyncio
from . import FrontInterface
from websockets.server import serve, ServerConnection
from websockets.exceptions import ConnectionClosedOK, ConnectionClosed
import logging

logger = logging.getLogger(__name__ + ".SocketFront")


class WSServer(FrontInterface):
    def __init__(
        self, q_data: asyncio.Queue, q_control: asyncio.Queue, host: str, port: int
    ):
        self.q_data: asyncio.Queue = q_data
        self.q_control: asyncio.Queue = q_control
        self.host = host
        self.port = port
        self.conn_data: dict[ServerConnection, asyncio.Queue] = (
            {}
        )  # Store data subscribers

    def getDataQueue(self) -> asyncio.Queue:
        return self.q_data

    async def send_data(self, ws) -> None:
        while True:
            data = await self.conn_data[ws].get()  # Wait for new data
            await ws.send(data)  # Might not need to await
            logger.debug(f"sent={data}")

    async def receive_control(self, ws) -> None:
        while True:
            control = await ws.recv()
            await self.q_control.put(control)
            logger.debug(f"received={control}")

    async def handle(self, ws) -> None:
        logger.info(
            f"client connected-> uuid={ws.id} remote_addr={ws.remote_address} local_addr={ws.local_address}"
        )
        # Add new data subscriber
        self.conn_data[ws] = asyncio.Queue()
        # Start the async coroutines
        send_task = asyncio.create_task(self.send_data(ws))
        receive_task = asyncio.create_task(self.receive_control(ws))

        try:
            # Wait for the coroutines to end/raise an exception
            await asyncio.gather(send_task, receive_task)
        except (ConnectionClosed, ConnectionClosedOK):
            logger.info(
                f"client disconnected-> uuid={ws.id} remote_addr={ws.remote_address} local_addr={ws.local_address}"
            )
        except Exception as e:
            logger.warning(f"an error occured in handle(): {e}")
        finally:
            send_task.cancel()
            receive_task.cancel()
            del self.conn_data[ws]
            await asyncio.gather(send_task, receive_task, return_exceptions=True)

    async def run(self) -> None:
        logger.info("starting WS server")
        async with serve(self.handle, self.host, self.port) as server:
            # Send data to each client subscriber
            while True:
                data = await self.q_data.get()
                for q_data in self.conn_data.values():
                    await q_data.put(data)

            # await server.serve_forever()
