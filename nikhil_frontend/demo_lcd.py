#!/usr/bin/env python3
import time
from RPLCD.i2c import CharLCD
import RPi.GPIO as GPIO

# Clean up any existing GPIO setup
try:
    GPIO.cleanup()
except:
    pass

# Set up GPIO
GPIO.setmode(GPIO.BCM)

# Simulate ADC reading with button presses
counter = 0
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
except Exception as e:
    print(f"LCD Error: {e}")
    exit()

# Update display
def update_display():
    lcd.clear()
    lcd.cursor_pos = (0, 0)
    lcd.write_string("POT Counter")
    lcd.cursor_pos = (1, 0)
    lcd.write_string(f"Value: {counter}")
    print(f"Counter: {counter}")

print("Potentiometer simulation")
print("Button 17: Increase counter")
print("Button 22: Decrease counter")
update_display()

try:
    # Track previous states
    prev_state_17 = GPIO.input(17)
    prev_state_22 = GPIO.input(22)
    
    while True:
        # Read current states
        state_17 = GPIO.input(17)
        state_22 = GPIO.input(22)
        
        # Button 17 pressed - increase counter
        if prev_state_17 == GPIO.HIGH and state_17 == GPIO.LOW:
            counter = min(1023, counter + 10)
            update_display()
            time.sleep(0.1)  # Debounce
            
        # Button 22 pressed - decrease counter
        if prev_state_22 == GPIO.HIGH and state_22 == GPIO.LOW:
            counter = max(0, counter - 10)
            update_display()
            time.sleep(0.1)  # Debounce
        
        # Update previous states
        prev_state_17 = state_17
        prev_state_22 = state_22
        
        time.sleep(0.05)
        
except KeyboardInterrupt:
    print("\nTest stopped by user")
finally:
    lcd.clear()
    GPIO.cleanup()
    print("Cleanup complete")
