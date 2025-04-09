#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time
from RPLCD.i2c import CharLCD
import pi-plates.ADCplate as ADC

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

# Clean up any existing GPIO setup
try:
    GPIO.cleanup()
except:
    pass

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

try:
    # Get first reading
    initial_voltage = ADC.getADC(0, 0)  # (board, channel)
    initial_value = int(initial_voltage * 1023 / 5.0)
    update_display(initial_value, initial_voltage)
    
    # Main loop
    while True:
        # Read potentiometer from ADC channel 0
        voltage = ADC.getADC(0, 0)  # (board, channel)
        
        # Convert voltage (0-5V) to range (0-1023)
        value = int(voltage * 1023 / 5.0)
        
        # Update display only when value changes
        if value != initial_value:
            update_display(value, voltage)
            initial_value = value
        
        # Short delay
        time.sleep(0.1)
        
except KeyboardInterrupt:
    print("\nTest stopped by user")
except Exception as e:
    print(f"Error: {e}")
finally:
    # Clean up
    lcd.clear()
    GPIO.cleanup()
    print("Cleanup complete")
