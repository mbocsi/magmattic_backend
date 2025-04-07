#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time
from RPLCD.i2c import CharLCD

# Initialize counter
counter = 0

# Clean up any existing GPIO setup
try:
    GPIO.cleanup()
except:
    pass

# Set up GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # UP button
GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # DOWN button

# Initialize LCD
try:
    lcd = CharLCD(
        i2c_expander='PCF8574',
        address=0x27,     
        port=1,
        cols=16,
        rows=2,
        dotsize=8
    )
    lcd.clear()
    lcd_available = True
except Exception as e:
    print(f"LCD Error: {e}")
    lcd_available = False

# Display the counter
def update_display():
    print(f"Counter: {counter}")
    if lcd_available:
        lcd.clear()
        lcd.cursor_pos = (0, 0)
        lcd.write_string("Button Test")
        lcd.cursor_pos = (1, 0)
        lcd.write_string(f"Count: {counter}")

print("Button counter test - press buttons")
print("Button 17: Increase counter")
print("Button 22: Decrease counter")
print("Ctrl+C to exit")

update_display()

try:
    # Track previous states for edge detection
    prev_state_17 = GPIO.input(17)
    prev_state_22 = GPIO.input(22)
    
    while True:
        # Read current states
        state_17 = GPIO.input(17)
        state_22 = GPIO.input(22)
        
        # Button 17 pressed (HIGH to LOW transition with pull-up)
        if prev_state_17 == GPIO.HIGH and state_17 == GPIO.LOW:
            counter += 1
            print("BUTTON 17 PRESSED - COUNT UP")
            update_display()
            time.sleep(0.2)  # Debounce
            
        # Button 22 pressed (HIGH to LOW transition with pull-up)
        if prev_state_22 == GPIO.HIGH and state_22 == GPIO.LOW:
            counter -= 1
            print("BUTTON 22 PRESSED - COUNT DOWN")
            update_display()
            time.sleep(0.2)  # Debounce
        
        # Update previous states
        prev_state_17 = state_17
        prev_state_22 = state_22
        
        # Short delay
        time.sleep(0.05)
        
except KeyboardInterrupt:
    print("\nButton test stopped by user")
finally:
    if lcd_available:
        lcd.clear()
    GPIO.cleanup()
    print("Cleanup complete")
