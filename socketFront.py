import asyncio
from frontInterface import FrontInterface

class SocketFront(FrontInterface):
    def __init__(self, q_data : asyncio.Queue, q_control : asyncio.Queue):
        self.q_data = q_data
        self.q_data = q_control
    
    async def update_data(self, data) -> None:
        raise NotImplementedError()
    
    async def run(self) -> None:
        raise NotImplementedError()