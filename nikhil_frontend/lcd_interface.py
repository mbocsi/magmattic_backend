from abc import ABC, abstractmethod

class LCDInterface(ABC):
    """Base interface for LCD display controllers"""
    
    @abstractmethod
    async def initialize_display(self):
        """Set up the LCD display and GPIOs"""
        pass
    
    @abstractmethod
    def update_display(self, line1, line2):
        """Update the LCD display with text"""
        pass
    
    @abstractmethod
    async def process_data(self):
        """Process incoming data"""
        pass
    
    @abstractmethod
    async def cleanup(self):
        """Clean up resources"""
        pass
    
    @abstractmethod
    async def run(self):
        """Main run loop"""
        pass
