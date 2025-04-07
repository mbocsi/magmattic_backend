#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time
from RPLCD.i2c import CharLCD

# Initialize LCD
lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, 
             cols=16, rows=2, dotsize=8)

# Set up GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Button 1 - increase
GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Button 2 - decrease

# Initialize counter (simulating potentiometer)
counter = 0
step_size = 10  # Increase/decrease by this amount
last_b1_state = GPIO.input(17)
last_b2_state = GPIO.input(22)

try:
    # Initial display
    lcd.clear()
    lcd.cursor_pos = (0, 0)
    lcd.write_string("Pot Simulation")
    lcd.cursor_pos = (1, 0)
    lcd.write_string(f"Value: {counter}")
    print("Potentiometer simulation running")
    print("Button 17: Increase, Button 22: Decrease")
    
    while True:
        # Read button states
        b1_state = GPIO.input(17)
        b2_state = GPIO.input(22)
        
        # Button 1 pressed (increase)
        if b1_state == GPIO.LOW and last_b1_state == GPIO.HIGH:
            counter = min(1023, counter + step_size)
            print(f"Value increased to: {counter}")
            time.sleep(0.2)  # Debounce
        
        # Button 2 pressed (decrease)
        if b2_state == GPIO.LOW and last_b2_state == GPIO.HIGH:
            counter = max(0, counter - step_size)
            print(f"Value decreased to: {counter}")
            time.sleep(0.2)  # Debounce
        
        # Update LCD
        lcd.cursor_pos = (1, 0)
        lcd.write_string(f"Value: {counter}   ")
        
        # Save button states
        last_b1_state = b1_state
        last_b2_state = b2_state
        
        # Short delay
        time.sleep(0.05)
        
except KeyboardInterrupt:
    print("\nTest stopped by user")
finally:
    lcd.clear()
    GPIO.cleanup()
    print("Test complete")
