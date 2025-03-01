
# author nikhil gudladana
from RPLCD.i2c import CharLCD
from time import sleep
import RPi.GPIO as GPIO

# Initialize the LCD with I2C
lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, 
             cols=16, rows=2, dotsize=8)

# Set up GPIO for button
BUTTON_PIN = 17  # GPIO pin number (change as needed)
GPIO.setmode(GPIO.BCM)  # Use BCM numbering
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Set up with pull-up resistor

# Initialize counter
counter = 0
last_button_state = GPIO.input(BUTTON_PIN)

try:
    while True:
        # Check button state
        button_state = GPIO.input(BUTTON_PIN)
        
        # Button press detected (LOW due to pull-up)
        if button_state == GPIO.LOW and last_button_state == GPIO.HIGH:
            counter += 1
            # Debounce
            sleep(0.05)
        
        last_button_state = button_state
        
        # Update display
        lcd.clear()
        lcd.cursor_pos = (0, 0)
        lcd.write_string("Button counter:")
        lcd.cursor_pos = (1, 0)
        lcd.write_string(f"Count: {counter}")
        
        sleep(0.1)  # Small delay to prevent LCD flicker
        
except KeyboardInterrupt:
    print("Cleaning up!")
    lcd.clear()
finally:
    # Clean up
    lcd.clear()
    GPIO.cleanup()  # Release GPIO resources
