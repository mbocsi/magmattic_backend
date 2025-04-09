#!/usr/bin/env python3
import asyncio
import time
from RPLCD.i2c import CharLCD
import piplates.ADCplate as ADC

# Initialize LCD
lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, cols=16, rows=2, dotsize=8)
lcd.clear()

async def main():
    print("Potentiometer test running - turn POT1 to see values change")
    print("Press Ctrl+C to exit")
    
    try:
        while True:
            # Read potentiometer
            raw_value = ADC.getADC(0, 0)  # board 0, channel 0
            pot_value = int(raw_value * 1023 / 5.0)  # Scale to 0-1023
                
            # Update LCD
            lcd.clear()
            lcd.cursor_pos = (0, 0)
            lcd.write_string(f"POT1 Value: {pot_value}")
            lcd.cursor_pos = (1, 0)
            lcd.write_string(f"Voltage: {raw_value:.2f}V")
                
            # Print to terminal
            print(f"POT1: {pot_value} (0-1023), Voltage: {raw_value:.2f}V")
            
            await asyncio.sleep(0.2)
    
    except KeyboardInterrupt:
        print("\nTest stopped by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        lcd.clear()
        print("Test complete")

if __name__ == "__main__":
    asyncio.run(main())
