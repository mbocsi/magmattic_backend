import spidev
import time
import RPi.GPIO as GPIO
from RPLCD.i2c import CharLCD

# Initialize SPI
spi = spidev.SpiDev()
spi.open(0, 0)  # Open SPI bus 0, device 0
spi.max_speed_hz = 1000000

# LCD Configuration
lcd = CharLCD(
    i2c_expander='PCF8574',
    address=0x27,     
    port=1,
    cols=16,
    rows=2,
    dotsize=8
)

def read_adc(channel):
    # Read MCP3008 ADC
    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    data = ((adc[1] & 3) << 8) + adc[2]
    return data

def main():
    try:
        while True:
            # Read potentiometer on channel 0
            pot_value = read_adc(0)
            
            # Clear LCD
            lcd.clear()
            
            # Display value
            lcd.cursor_pos = (0, 0)
            lcd.write_string(f"POT: {pot_value}")
            
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("Test stopped")
    finally:
        lcd.clear()
        spi.close()

if __name__ == "__main__":
    main()
