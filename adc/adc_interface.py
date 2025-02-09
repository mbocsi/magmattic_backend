from abc import ABC, abstractmethod

class ADCInterface(ABC):
    @abstractmethod
    async def run(self) -> None:
        ...