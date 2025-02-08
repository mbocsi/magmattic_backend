from abc import ABC, abstractmethod

class FrontInterface(ABC):
    @abstractmethod
    async def run(self) -> None:
        pass
