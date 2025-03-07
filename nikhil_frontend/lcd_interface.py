from abc import ABC, abstractmethod
from app_interface import AppComponent

class LCDInterface(AppComponent):
    """
    Abstract base class for LCD display interfaces.
    Extends AppComponent to match Marton's architecture.
    """
    
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
