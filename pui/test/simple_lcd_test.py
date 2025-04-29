#!/usr/bin/env python3
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

print("Pi-Plates ADC Potentiometer Test")
print("Turn the potentiometer to see values change")
print("Press Ctrl+C to exit")

try:
    while True:
        # Read from channel 0 on board 0
        raw_value = ADC.getADC(0, 0)
        
        # Scale to 0-1023 range, ensuring upper limit
        pot_value = min(1023, int(raw_value * 1023 / 5.0))
        
        # Update LCD
        lcd.clear()
        lcd.cursor_pos = (0, 0)
        lcd.write_string(f"POT Value: {pot_value}")
        lcd.cursor_pos = (1, 0)
        lcd.write_string(f"Voltage: {raw_value:.2f}V")
        
        # Print to terminal
        print(f"POT: {pot_value} (0-1023), Voltage: {raw_value:.2f}V")
        
        time.sleep(0.2)

except KeyboardInterrupt:
    print("\nTest stopped by user")
finally:
    lcd.clear()
    print("Test complete")
