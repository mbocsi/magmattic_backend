from abc import ABC


class AppComponent(ABC):
    async def run(self) -> None: ...
