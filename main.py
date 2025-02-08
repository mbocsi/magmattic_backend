import asyncio
from frontInterface import FrontInterface
from socketFront import SocketFront
from adc import ADC

class Magmattic:
    def __init__(self, front : FrontInterface, adc : ADC) -> None:
        self.gui = front
        self.adc = adc
    
    async def run(self) -> None:
       await asyncio.gather(*(self.gui.run(), self.adc.run()))

if __name__ == "__main__":
    q_data = asyncio.Queue()
    q_control = asyncio.Queue()
    front = SocketFront(q_data, q_control, host="localhost", port=8888)
    # front = KtinkerFront(q_data, q_control)
    adc = ADC(q_data, q_control)
    app = Magmattic(front, adc)
    print("Starting app!")
    asyncio.run(app.run())