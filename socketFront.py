import asyncio
from frontInterface import FrontInterface
from websockets.server import serve
from websockets.exceptions import ConnectionClosedOK

class SocketFront(FrontInterface):
    def __init__(self, q_data : asyncio.Queue, q_control : asyncio.Queue, host: str = "localhost", port: int = 8888):
        self.q_data : asyncio.Queue = q_data
        self.q_control : asyncio.Queue = q_control
        self.host = host
        self.port = port
    
    async def send_data(self, ws) -> None:
        while True:
            try:
                data = await self.q_control.get()
                await ws.send(data)
            except ConnectionClosedOK:
                break
    
    async def receive_control(self, ws) -> None:
        async for control in ws:
            print(f"Received: {control}")
            self.q_control.put_nowait(control)

    async def handle(self, ws) -> None:
        print("Client connected!")
        send_task = asyncio.create_task(self.send_data(ws))
        receive_task = asyncio.create_task(self.receive_control(ws))
        results = await asyncio.gather(send_task, receive_task)
    
    async def run(self) -> None:
        async with serve(self.handle, self.host, self.port) as server:
            print(f"Starting ws server on {self.host}:{self.port}")
            await server.serve_forever()