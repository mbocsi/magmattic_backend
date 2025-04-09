#!/usr/bin/env python3
import sys
import os
import time
from RPLCD.i2c import CharLCD

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import directly from the adc component
try:
    from adc.adc_component import ADCComponent
    print("Successfully imported ADCComponent")
    use_adc_component = True
except ImportError as e:
    print(f"Could not import ADCComponent: {e}")
    use_adc_component = False

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
    print("LCD initialized successfully")
except Exception as e:
    print(f"LCD Error: {e}")
    exit(1)

# Display on LCD
def update_display(line1, line2):
    try:
        lcd.clear()
        lcd.cursor_pos = (0, 0)
        lcd.write_string(line1[:16])
        lcd.cursor_pos = (1, 0)
        lcd.write_string(line2[:16])
        print(f"{line1} | {line2}")
    except Exception as e:
        print(f"Display error: {e}")

print("ADC Reading Test")
print("Press Ctrl+C to exit")

try:
    if use_adc_component:
        # Create a dummy queue
        import asyncio
        q = asyncio.Queue()
        
        # Create ADC component (with dummy queue)
        adc = ADCComponent(pub_queue=q, sub_queue=q)
        
        # Test if ADC is connected
        adc_id = adc.ADC.getID(adc.addr)
        if adc_id:
            update_display("ADC Connected", f"ID: {adc_id}")
            time.sleep(2)
        else:
            update_display("ADC Not Found", "Check connection")
            time.sleep(2)
        
        # Read values
        counter = 0
        while True:
            try:
                # Try to read ADC value directly using imported ADC
                if hasattr(adc.ADC, 'getADC'):
                    value = adc.ADC.getADC(adc.addr, 0)  # Channel 0
                    pot_value = int(value * 1023 / 5.0)
                    update_display(f"POT: {pot_value}", f"Volt: {value:.2f}V")
                else:
                    update_display("ERROR:", "No getADC method")
            except Exception as e:
                update_display("ADC Read Error", str(e)[:16])
            
            counter += 1
            if counter % 10 == 0:
                print(f"Completed {counter} readings")
                
            time.sleep(0.2)
    else:
        # Fallback to direct access attempt
        try:
            # Try different import path
            sys.path.append('/home/magmattic/Documents/magmattic_backend')
            import piplates.ADCplate as ADC
            print("Successfully imported piplates.ADCplate")
            
            while True:
                try:
                    value = ADC.getADC(0, 0)  # Board 0, channel 0
                    pot_value = int(value * 1023 / 5.0)
                    update_display(f"POT: {pot_value}", f"Volt: {value:.2f}V")
                except Exception as e:
                    update_display("ADC Read Error", str(e)[:16])
                time.sleep(0.2)
        except ImportError:
            update_display("No ADC module", "Path issue")
            print("Could not import piplates module even with modified path")
            time.sleep(5)
            
            # Just use button simulation as last resort
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Increase value
            GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Decrease value
            
            pot_value = 512  # Start in middle
            update_display("SIMULATED POT", f"Value: {pot_value}")
            
            prev_17 = GPIO.input(17)
            prev_22 = GPIO.input(22)
            
            while True:
                btn_17 = GPIO.input(17)
                btn_22 = GPIO.input(22)
                
                if prev_17 == GPIO.HIGH and btn_17 == GPIO.LOW:
                    pot_value = min(1023, pot_value + 10)
                    update_display("SIMULATED POT", f"Value: {pot_value}")
                    time.sleep(0.2)
                
                if prev_22 == GPIO.HIGH and btn_22 == GPIO.LOW:
                    pot_value = max(0, pot_value - 10)
                    update_display("SIMULATED POT", f"Value: {pot_value}")
                    time.sleep(0.2)
                
                prev_17 = btn_17
                prev_22 = btn_22
                
                time.sleep(0.05)
            
except KeyboardInterrupt:
    print("\nTest stopped by user")
except Exception as e:
    print(f"Error: {e}")
finally:
    try:
        lcd.clear()
        if 'GPIO' in globals():
            GPIO.cleanup()
        print("Cleanup complete")
    except:
        pass
