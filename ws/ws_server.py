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
        """
        WebSocket component for handling bi-directional communication with connected clients.

        Args:
            pub_queue (asyncio.Queue): Queue for publishing messages to other components.
            sub_queue (asyncio.Queue): Queue for receiving messages (not used here).
            host (str): Host IP address to bind the WebSocket server to.
            port (int): Port number to listen on.
        """
        self.pub_queue: asyncio.Queue = pub_queue
        self.sub_queue: asyncio.Queue = sub_queue
        self.host = host
        self.port = port

        # Maps active connections to their individual outbound queues
        self.conn_data: dict[ServerConnection, asyncio.Queue] = {}

    async def send(self, ws) -> None:
        """
        Sends messages from the internal queue to a specific WebSocket client.

        Args:
            ws: WebSocket connection instance.
        """
        while True:
            data = await self.conn_data[ws].get()  # Wait for new data
            await ws.send(json.dumps(data))  # Might not need to await

    async def recv(self, ws) -> None:
        """
        Receives and processes messages from a WebSocket client.
        If message is a subscription request, injects the client's queue.

        Args:
            ws: WebSocket connection instance.
        """
        while True:
            data = await ws.recv()
            try:
                data = json.loads(data)
                if data["topic"] == "subscribe":
                    data["payload"]["sub_queue"] = self.conn_data[
                        ws
                    ]  # Inject the queue
                await self.pub_queue.put(data)
            except json.JSONDecodeError as e:
                logger.warning(f"Error decoding JSON: {e}")

    async def handle(self, ws) -> None:
        """
        Handles a new WebSocket client connection. Starts tasks for sending and receiving.

        Args:
            ws: WebSocket connection instance.
        """
        logger.info(
            f"client connected-> uuid={ws.id} remote_addr={ws.remote_address} local_addr={ws.local_address}"
        )

        self.conn_data[ws] = asyncio.Queue()  # Initialize client queue

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
            await self.pub_queue.put(
                {"topic": "unsubscribe", "payload": self.conn_data[ws]}
            )
            del self.conn_data[ws]
            await asyncio.gather(send_task, receive_task, return_exceptions=True)

    async def run(self) -> None:
        """
        Entry point for starting the WebSocket server. Binds to the host and port.
        """
        logger.info("starting WS server")
        async with serve(self.handle, self.host, self.port) as server:
            await server.serve_forever()
