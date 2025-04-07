#!/usr/bin/env python3
import piplates.ADCplate as ADC
import time
from RPLCD.i2c import CharLCD

# Initialize LCD
try:
    lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, cols=16, rows=2)
    lcd.clear()
except Exception as e:
    print(f"LCD Error: {e}")
    exit()

print("Simple Potentiometer Test")

try:
    while True:
        # Read ADC value and voltage
        adc_value = ADC.getADC(0, 0)  # board 0, channel 0
        voltage = ADC.getVOLT(0, 0)
        
        # Display on LCD
        lcd.clear()
        lcd.cursor_pos = (0, 0)
        lcd.write_string(f"ADC: {adc_value}")
        lcd.cursor_pos = (1, 0)
        lcd.write_string(f"Volt: {voltage:.2f}V")
        
        # Print to console
        print(f"ADC: {adc_value}, Voltage: {voltage:.2f}V")
        
        time.sleep(0.5)
        
except KeyboardInterrupt:
    lcd.clear()
    print("Test stopped")
except Exception as e:
    print(f"Error: {e}")
finally:
    lcd.clear()
