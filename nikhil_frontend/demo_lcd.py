from RPLCD.i2c import CharLCD
from time import sleep

# Initialize the LCD with I2C
lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, 
             cols=16, rows=2, dotsize=8)

try:
    while True:
        # Writing to display
        print("Writing to display")
        lcd.clear()
        lcd.cursor_pos = (0, 0)  # First line, first position
        lcd.write_string("Greetings!")
        lcd.cursor_pos = (1, 0)  # Second line, first position
        lcd.write_string("Demo Code")
        sleep(2)
        
        lcd.clear()
        lcd.cursor_pos = (0, 0)
        lcd.write_string("I am a display!")
        sleep(2)
        
        lcd.clear()
        sleep(2)
except KeyboardInterrupt:
    print("Cleaning up!")
    lcd.clear()
finally:
    # Make sure to clear the display even if an error occurs
    lcd.clear()
