import piplates.ADCplate as ADC
from RPLCD.i2c import CharLCD
from time import sleep
import RPi.GPIO as GPIO

# Initialize LCD
lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, 
             cols=16, rows=2, dotsize=8)

# Initialize pot value
pot_value = 0

# Display the potentiometer value
def update_display(value):
    lcd.clear()
    lcd.cursor_pos = (0, 0)
    lcd.write_string("Pot Value:")
    lcd.cursor_pos = (1, 0)
    lcd.write_string(f"{value}")

try:
    while True:
        # Read potentiometer value from channel 0
        pot_value = ADC.getADC(0, 0)  # (board, channel)
        
        # Update display
        update_display(pot_value)
        
        # Print to console for debugging
        print(f"Potentiometer Value: {pot_value}")
        
        # Short delay
        sleep(0.1)
        
except KeyboardInterrupt:
    print("Cleaning up!")
    lcd.clear()
finally:
    lcd.clear()
    # No GPIO cleanup needed for ADC reading
