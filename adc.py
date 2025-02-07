import asyncio
class ADC:
    def __init__(self, q_data : asyncio.Queue , q_control : asyncio.Queue):
        self.q_data = q_data
        self.q_control = q_control
    
    async def get_reading(self) -> None:
        raise NotImplementedError()
    
    async def run(self) -> None:
        raise NotImplementedError()