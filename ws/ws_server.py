import asyncio
from app_interface import AppComponent
from websockets.server import serve, ServerConnection
from websockets.exceptions import ConnectionClosedOK, ConnectionClosed
import logging
import json

logger = logging.getLogger(__name__)


class WebSocketComponent(AppComponent):
    def __init__(
        self, pub_queue: asyncio.Queue, sub_queue: asyncio.Queue, host: str, port: int
    ):
        self.pub_queue: asyncio.Queue = pub_queue
        self.sub_queue: asyncio.Queue = sub_queue
        self.host = host
        self.port = port
        self.conn_data: dict[ServerConnection, asyncio.Queue] = (
            {}
        )  # Store data subscribers

    async def send(self, ws) -> None:
        while True:
            data = await self.conn_data[ws].get()  # Wait for new data
            await ws.send(json.dumps(data))  # Might not need to await

    async def recv(self, ws) -> None:
        while True:
            data = await ws.recv()
            try:
                data = json.loads(data)
                await self.pub_queue.put(data)
            except json.JSONDecodeError as e:
                logger.warning(f"Error decoding JSON: {e}")

    async def handle(self, ws) -> None:
        logger.info(
            f"client connected-> uuid={ws.id} remote_addr={ws.remote_address} local_addr={ws.local_address}"
        )
        # Add new data subscriber
        self.conn_data[ws] = asyncio.Queue()
        # Start the async coroutines
        send_task = asyncio.create_task(self.send(ws))
        receive_task = asyncio.create_task(self.recv(ws))

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
                data = await self.sub_queue.get()
                for q_data in self.conn_data.values():
                    await q_data.put(data)

            # await server.serve_forever()
