#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time
from RPLCD.i2c import CharLCD
import piplates.ADCplate as ADC

# Initialize LCD
lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, 
             cols=16, rows=2, dotsize=8)

# Set up GPIO (for exit button if needed)
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Use as exit button

# Initialize variables
pot_value = 0
last_pot_value = -1  # Force initial update
counter = 0

# ADC settings
ADC_ADDR = 0        # Pi-Plates ADC board address (usually 0)
ADC_CHANNEL = 0     # Channel for POT1 (D0)

try:
    # Initial display
    lcd.clear()
    lcd.cursor_pos = (0, 0)
    lcd.write_string("POT Test Running")
    lcd.cursor_pos = (1, 0)
    lcd.write_string("Value: 0")
    print("Potentiometer test running - Ctrl+C to exit")
    
    while True:
        # Read potentiometer value from ADC
        try:
            # Get raw ADC reading (0-5V mapped to 0-4095)
            raw_value = ADC.getADC(ADC_ADDR, ADC_CHANNEL)
            
            # Map to 0-1023 range
            pot_value = int(raw_value * 1023 / 4095)
            
            # Constrain to 0-1023 range
            pot_value = max(0, min(1023, pot_value))
            
            # Update counter based on pot value (linear mapping)
            counter = pot_value
            
        except Exception as e:
            print(f"ADC reading error: {e}")
            # If ADC fails, increment counter slowly for testing
            counter = (counter + 1) % 1024
            time.sleep(0.2)
        
        # Display counter value if changed
        if counter != last_pot_value:
            # Update LCD
            lcd.cursor_pos = (1, 0)
            lcd.write_string(f"Value: {counter:4d}    ")
            
            # Print to console
            print(f"Potentiometer value: {counter}")
            
            last_pot_value = counter
        
        # Check if exit button pressed
        if GPIO.input(17) == GPIO.LOW:
            print("Exit button pressed - ending test")
            break
            
        # Short delay
        time.sleep(0.1)
        
except KeyboardInterrupt:
    print("\nPotentiometer test stopped by user")
finally:
    # Clean up
    lcd.clear()
    lcd.cursor_pos = (0, 0)
    lcd.write_string("Test Complete")
    time.sleep(1)
    lcd.clear()
    GPIO.cleanup()
    print("Test complete, GPIO cleaned up")
