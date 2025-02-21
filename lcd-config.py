# LCD Display Configuration
LCD_WIDTH = 16  # Characters per line
LCD_HEIGHT = 2  # Number of lines

# I2C Configuration 
I2C_ADDR = 0x27  # Standard I2C address for most 16x2 LCDs
I2C_BUS = 1      # RPi default I2C bus

# GPIO Pin Configuration
BUTTON_UP = 17    # GPIO pin for UP button
BUTTON_DOWN = 27  # GPIO pin for DOWN button
BUTTON_SELECT = 22  # GPIO pin for SELECT button
BUTTON_BACK = 23   # GPIO pin for BACK button

# Display Update Settings
UPDATE_INTERVAL = 0.1  # How often to update display (seconds)
SCROLL_INTERVAL = 0.3  # Time between menu scrolls
BUFFER_SIZE = 100     # Number of samples to keep in buffer

# Menu Configuration
MENU_ITEMS = [
    'Voltage View',
    'FFT View',
    'Settings',
    'Info'
]

# Thread Settings
IO_TIMEOUT = 0.5      # Timeout for I/O operations

# Display Modes
DISPLAY_MODES = {
    'VOLTAGE': 'voltage',
    'FFT': 'fft'
}

# Logging
LOG_LEVEL = 'INFO'
