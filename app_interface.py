from abc import ABC


class AppInterface(ABC):
    async def run(self) -> None: ...
