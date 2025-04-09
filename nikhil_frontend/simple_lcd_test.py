#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time
from RPLCD.i2c import CharLCD
import piplates.ADCplate as ADC

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
    exit(1)

# Clean up any existing GPIO
try:
    GPIO.cleanup()
except:
    pass

# Set up GPIO
GPIO.setmode(GPIO.BCM)

# Function to update display
def update_display(value, voltage):
    lcd.clear()
    lcd.cursor_pos = (0, 0)
    lcd.write_string(f"POT Value: {value}")
    lcd.cursor_pos = (1, 0)
    lcd.write_string(f"Voltage: {voltage:.2f}V")
    print(f"POT Value: {value}, Voltage: {voltage:.2f}V")

print("Potentiometer test running")
print("Turn the potentiometer to see value change")
print("Press Ctrl+C to exit")

try:
    while True:
        # Read from ADC channel 0
        voltage = ADC.getADC(0, 0)  # (board, channel)
        
        # Convert to 0-1023 range
        pot_value = int(voltage * 1023 / 5.0)
        
        # Update the display
        update_display(pot_value, voltage)
        
        # Short delay
        time.sleep(0.2)

except KeyboardInterrupt:
    print("\nTest stopped by user")
finally:
    lcd.clear()
    GPIO.cleanup()
    print("Cleanup complete")
