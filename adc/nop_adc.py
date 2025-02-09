from . import ADCInterface
import asyncio

class NopADC(ADCInterface):
    def __init__(self):
        ...
    async def run(self) -> None:
        while True:
            # voltage = random.uniform(0, 10)
            # self.q_data.put_nowait(json.dumps({'v': voltage}))
            await asyncio.sleep(1)