#!/usr/bin/env python3
import time
import sys
import os
from RPLCD.i2c import CharLCD

# Add the project root to path to find modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try importing the ADC from the adc module
try:
    import piplates.ADCplate as ADC
    print("Successfully imported Pi-Plates ADCplate")
    
    def read_adc():
        try:
            value = ADC.getADC(0, 0)  # board 0, channel 0
            return value, None
        except Exception as e:
            return None, str(e)
            
except ImportError:
    print("Pi-Plates import failed, trying alternative imports...")
    
    # Try to find ADC in project code
    try:
        # Look for the ADC in the adc folder which exists in the project
        from adc.adc_async import getStreamSync  # or other functions
        import adc.adc_async as ADC
        print("Successfully imported project ADC module")
        
        def read_adc():
            try:
                # This may need adjustment based on actual available functions
                value = ADC.getADC(0, 0) if hasattr(ADC, 'getADC') else 2.5
                return value, None
            except Exception as e:
                return None, str(e)
                
    except ImportError:
        print("WARNING: No ADC module found. Using simulated values.")
        
        def read_adc():
            # Just return mid-range value and indicate simulation
            return 2.5, "Using simulated ADC values"

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

# Display the potentiometer value
def update_display(value, voltage, error_msg=None):
    try:
        lcd.clear()
        lcd.cursor_pos = (0, 0)
        lcd.write_string(f"POT: {value}")
        lcd.cursor_pos = (1, 0)
        if error_msg:
            lcd.write_string(f"ERROR: See log")
            print(f"ERROR: {error_msg}")
        else:
            lcd.write_string(f"Voltage: {voltage:.2f}V")
            print(f"POT: {value}, Voltage: {voltage:.2f}V")
    except Exception as e:
        print(f"Display Error: {e}")

print("Potentiometer test - rotate to see values")
print("Press Ctrl+C to exit")

try:
    # Initial reading
    initial_voltage, error = read_adc()
    if error:
        print(f"Initial reading error: {error}")
    
    initial_value = int(initial_voltage * 1023 / 5.0) if initial_voltage is not None else 512
    update_display(initial_value, initial_voltage or 2.5, error)
    
    # Main loop
    last_value = initial_value
    while True:
        voltage, error = read_adc()
        
        if voltage is not None:
            value = int(voltage * 1023 / 5.0)
            
            # Update display if value changed
            if abs(value - last_value) > 5:
                update_display(value, voltage, error)
                last_value = value
        else:
            update_display(last_value, 0, error)
        
        time.sleep(0.2)
        
except KeyboardInterrupt:
    print("\nTest stopped by user")
except Exception as e:
    print(f"Error: {e}")
finally:
    try:
        lcd.clear()
        print("Cleanup complete")
    except:
        pass
