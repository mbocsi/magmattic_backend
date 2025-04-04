#!/usr/bin/env python3
"""
Simple LCD test - displays basic text on LCD
"""
import time
from RPLCD.i2c import CharLCD
import RPi.GPIO as GPIO

# Initialize the LCD
try:
    # Try with common settings
    lcd = CharLCD(
        i2c_expander='PCF8574',
        address=0x27,     
        port=1,
        cols=16,
        rows=2,
        dotsize=8
    )

    lcd.clear()
    time.sleep(1)
    
    # Display test message
    lcd.cursor_pos = (0, 0)
    lcd.write_string("Hello World!")
    lcd.cursor_pos = (1, 0)
    lcd.write_string("LCD Test OK")
    
    print("Test message sent to LCD")
    print("Press Ctrl+C to exit")

    while True:
        time.sleep(1)
        
except KeyboardInterrupt:
    print("Test stopped by user")
    
except Exception as e:
    print(f"Error: {e}")
    
finally:
    # Clean up
    try:
        lcd.clear()
        GPIO.cleanup()
    except:
        pass
