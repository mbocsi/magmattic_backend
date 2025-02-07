from abc import ABC, abstractmethod
import asyncio

class FrontInterface(ABC):
    @abstractmethod
    async def update_data(self, data) -> None:
        pass
    
    @abstractmethod
    async def run(self) -> None:
        pass

class KtinkerFront(FrontInterface):
    def __init__(self, q_data : asyncio.Queue, q_control : asyncio.Queue):
        self.q_data = q_data
        self.q_control = q_control
        raise NotImplementedError()
    
    async def update_data(self, data) -> None:
        raise NotImplementedError()
    
    async def run(self) -> None:
        raise NotImplementedError()
