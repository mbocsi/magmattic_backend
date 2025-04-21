# Define state constants
class State:
    B_FIELD = 0
    FFT = 1
    ADJUSTING = 2
    OFF = 3


# GPIO Button Pin Configuration - using BCM mode
BUTTON_MODE = 17  # B1: Change mode button
BUTTON_POWER = 22  # B2: Power on/off

# Potentiometer Pins (ADC channels)
POT_DAT = 0  # POT1: Data acquisition time potentiometer (ADC channel 0)

# Display Configuration
LCD_WIDTH = 16
LCD_HEIGHT = 2
I2C_ADDR = 0x27
I2C_BUS = 1

# Data acquisition time constants
MIN_DAT = 0.1  # Minimum data acquisition time (seconds)
MAX_DAT = 100.0  # Maximum data acquisition time (seconds)
DEFAULT_DAT = 1.0  # Default data acquisition time (seconds)
