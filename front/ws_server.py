import asyncio
from . import FrontInterface
from websockets.server import serve
from websockets.exceptions import ConnectionClosedOK, ConnectionClosed
import logging

logger = logging.getLogger(__name__ + ".SocketFront")

class WSServer(FrontInterface):
    def __init__(self, q_data : asyncio.Queue, q_control : asyncio.Queue, host : str, port: int):
        self.q_data : asyncio.Queue = q_data
        self.q_control : asyncio.Queue = q_control
        self.host = host
        self.port = port
    
    async def send_data(self, ws) -> None:
        while True:
            data = await self.q_data.get() # Wait for new data
            await ws.send(data) # Might not need to await
            logger.debug(f"sent={data}")
    
    async def receive_control(self, ws) -> None:
        while True:
            control = await ws.recv()
            self.q_control.put_nowait(control)
            logger.debug(f"received={control}")

    async def handle(self, ws) -> None:
        logger.info(f"client connected-> uuid={ws.id} remote_addr={ws.remote_address} local_addr={ws.local_address}")
        # Instantiate async tasks
        send_task = asyncio.create_task(self.send_data(ws))
        receive_task = asyncio.create_task(self.receive_control(ws))

        try:
            await asyncio.gather(send_task, receive_task)
        except (ConnectionClosed, ConnectionClosedOK):
            logger.info(f"client disconnected-> uuid={ws.id} remote_addr={ws.remote_address} local_addr={ws.local_address}")
        except Exception as e:
            logger.warning(f"an error occured in handle(): {e}")
        finally:
            send_task.cancel()
            receive_task.cancel()
            await asyncio.gather(send_task, receive_task, return_exceptions=True)
    
    async def run(self) -> None:
        async with serve(self.handle, self.host, self.port) as server:
            await server.serve_forever()