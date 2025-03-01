from RPLCD.i2c import CharLCD
from time import sleep
import RPi.GPIO as GPIO

# Initialize LCD
lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, 
             cols=16, rows=2, dotsize=8)

# Set up button
BUTTON_PIN = 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Initialize counter
counter = 0
last_button_state = GPIO.input(BUTTON_PIN)
last_counter = -1  # Force initial display update

# Display the counter (only when it changes)
def update_display(count):
    lcd.clear()
    lcd.cursor_pos = (0, 0)
    lcd.write_string("Button counter:")
    lcd.cursor_pos = (1, 0)
    lcd.write_string(f"Count: {count}")

try:
    # Initial display
    update_display(counter)
    
    while True:
        # Check button state
        button_state = GPIO.input(BUTTON_PIN)
        
        # Button press detected (transition from HIGH to LOW)
        if button_state == GPIO.LOW and last_button_state == GPIO.HIGH:
            counter += 1
            print(f"Button pressed! Count: {counter}")  # Debug output
            
            # Update display only when counter changes
            update_display(counter)
            
            # Wait for button release to avoid multiple counts
            while GPIO.input(BUTTON_PIN) == GPIO.LOW:
                sleep(0.01)
                
            # Add additional debounce delay
            sleep(0.2)
        
        last_button_state = button_state
        sleep(0.01)  # Short delay in main loop
        
except KeyboardInterrupt:
    print("Cleaning up!")
    lcd.clear()
finally:
    lcd.clear()
    GPIO.cleanup()
