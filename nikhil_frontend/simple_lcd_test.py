#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time
from RPLCD.i2c import CharLCD
import piplates.ADCplate as ADC

# Initialize LCD
lcd = CharLCD(
    i2c_expander='PCF8574',
    address=0x27,
    port=1,
    cols=16,
    rows=2,
    dotsize=8
)
lcd.clear()

# Clean up any existing GPIO setup
GPIO.cleanup()

# Display the potentiometer value
def update_display(value, voltage):
    lcd.clear()
    lcd.cursor_pos = (0, 0)
    lcd.write_string(f"POT: {value}")
    lcd.cursor_pos = (1, 0)
    lcd.write_string(f"Voltage: {voltage:.2f}V")
    print(f"POT: {value}, Voltage: {voltage:.2f}V")

print("Potentiometer test - rotate to see values")
print("Press Ctrl+C to exit")

# Main loop
try:
    while True:
        # Read potentiometer from ADC channel 0
        voltage = ADC.getADC(0, 0)  # (board, channel)
        
        # Convert voltage (0-5V) to range (0-1023)
        value = int(voltage * 1023 / 5.0)
        
        # Update display
        update_display(value, voltage)
        
        # Short delay
        time.sleep(0.2)
        
except KeyboardInterrupt:
    print("\nTest stopped by user")
except Exception as e:
    print(f"Error: {e}")
finally:
    # Clean up
    lcd.clear()
    GPIO.cleanup()
    print("Cleanup complete")
