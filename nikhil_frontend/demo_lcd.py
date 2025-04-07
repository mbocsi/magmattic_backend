import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from RPLCD.i2c import CharLCD

# Initialize I2C bus
i2c = busio.I2C(board.SCL, board.SDA)

# Initialize ADS1115
ads = ADS.ADS1115(i2c)

# Initialize LCD
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
        # Use channel 0 of ADS1115
        channel = AnalogIn(ads, ADS.P0)
        
        while True:
            # Read raw value
            raw_value = channel.value
            
            # Clear LCD
            lcd.clear()
            
            # Display value
            lcd.cursor_pos = (0, 0)
            lcd.write_string(f"POT: {raw_value}")
            
            # Print to console
            print(f"Potentiometer Value: {raw_value}")
            
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("Test stopped")
    finally:
        lcd.clear()

if __name__ == "__main__":
    main()
