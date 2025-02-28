

import drivers
from time import sleep


display = drivers.Lcd()


try:
    while True:
        #  sentences = 16 characters long!
        print("Writing to display")
        display.lcd_display_string("Greetings Human!", 1)  
        display.lcd_display_string("Demo Pi Guy code", 2)  
        sleep(2)                                           
        display.lcd_display_string("I am a display!", 1)   
        sleep(2)                                           
        display.lcd_clear()                                
        sleep(2)                                           
except KeyboardInterrupt:
    print("Cleaning up!")
    display.lcd_clear()
