#!/usr/bin/env python3
from RPLCD.i2c import CharLCD
import time
import RPi.GPIO as GPIO
import sys
import piplates.ADCplate as ADC
from piplates.ADCplate import *  # type: ignore

# LCD Configuration
lcd = CharLCD(
    i2c_expander='PCF8574',
    address=0x27,     
    port=1,
    cols=16,
    rows=2,
    dotsize=8
)

def main():
    try:
        lcd.clear()
        
        while True:
            # Read potentiometer value from channel 0
            pot_value = ADC.getADC(0, 0)  # (board, channel)
            
            # Clear LCD
            lcd.clear()
            
            # Write potentiometer value
            lcd.cursor_pos = (0, 0)
            lcd.write_string(f"POT Value: {pot_value}")
            
            # Optional: show percentage
            percentage = (pot_value / 1023) * 100
            lcd.cursor_pos = (1, 0)
            lcd.write_string(f"Percent: {percentage:.1f}%")
            
            # Small delay
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("Test stopped by user")
    finally:
        lcd.clear()
        GPIO.cleanup()

if __name__ == "__main__":
    main()
