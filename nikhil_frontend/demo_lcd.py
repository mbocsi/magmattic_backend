import piplates.ADCplate as ADC
import time
from RPLCD.i2c import CharLCD

# LCD Configuration
lcd = CharLCD(
    i2c_expander='PCF8574',
    address=0x27,     
    port=1,
    cols=16,
    rows=2,
    dotsize=8
)

def read_adc(channel, addr=0):
    """Read ADC value from Pi-Plates ADC"""
    try:
        return ADC.getADC(addr, channel)
    except Exception as e:
        print(f"ADC reading error: {e}")
        return 0

def main():
    try:
        lcd.clear()
        print("ADC Potentiometer Test Started")
        
        while True:
            # Read potentiometer on channel 0
            pot_value = read_adc(0)
            
            # Clear LCD and display value
            lcd.clear()
            lcd.cursor_pos = (0, 0)
            lcd.write_string(f"POT: {pot_value}")
            
            # Also print to terminal for debugging
            print(f"Potentiometer Value: {pot_value}")
            
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("Test stopped")
    finally:
        lcd.clear()

if __name__ == "__main__":
    main()
