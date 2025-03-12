from abc import ABC, abstractmethod
import asyncio

class LCDInterface(ABC):
    """
    Abstract base class for LCD display interfaces.
    """
    
    @abstractmethod
    async def run(self) -> None:
        """Main run loop for the LCD interface"""
        pass
    
    @abstractmethod
    async def initialize_display(self) -> None:
        """Initialize the LCD display and GPIO pins"""
        pass
    
    @abstractmethod
    async def handle_button_press(self, button: int) -> None:
        """Handle button press events from GPIO"""
        pass
    
    @abstractmethod
    async def update_display(self, line1: str, line2: str) -> None:
        """Update both lines of the LCD display"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup GPIO and LCD resources"""
        pass
    
    @abstractmethod
    async def process_data(self) -> None:
        """Process incoming data from the queue"""
        pass
    
    @abstractmethod
    async def update_display_with_data(self) -> None:
        """Update display based on current view mode"""
        from abc import ABC, abstractmethod
import asyncio

class LCDInterface(ABC):
    """
    Abstract base class for LCD display interfaces.
    """
    
    @abstractmethod
    async def run(self) -> None:
        """Main run loop for the LCD interface"""
        pass
    
    @abstractmethod
    async def initialize_display(self) -> None:
        """Initialize the LCD display and GPIO pins"""
        pass
    
    @abstractmethod
    async def handle_button_press(self, button: int) -> None:
        """Handle button press events from GPIO"""
        pass
    
    @abstractmethod
    async def update_display(self, line1: str, line2: str) -> None:
        """Update both lines of the LCD display"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup GPIO and LCD resources"""
        pass
    
    @abstractmethod
    async def process_data(self) -> None:
        """Process incoming data from the queue"""
        pass
    
    @abstractmethod
    async def update_display_with_data(self) -> None:
        """Update display based on current view mode"""
        pass
