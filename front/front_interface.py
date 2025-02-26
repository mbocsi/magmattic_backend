from abc import ABC, abstractmethod
import asyncio


class FrontInterface(ABC):
    @abstractmethod
    async def run(self) -> None: ...
