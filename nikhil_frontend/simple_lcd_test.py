#!/usr/bin/env python3
import time
from RPLCD.i2c import CharLCD
import piplates.ADCplate as ADC

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

# Function to read from ADC with error handling
def read_adc():
    try:
        # Try to read the ADC
        value = ADC.getADC(0, 0)  # board 0, channel 0
        return value
    except Exception as e:
        print(f"ADC Read Error: {e}")
        return None  # Return None to indicate error

# Display the potentiometer value
def update_display(value, voltage):
    try:
        lcd.clear()
        lcd.cursor_pos = (0, 0)
        lcd.write_string(f"POT: {value}")
        lcd.cursor_pos = (1, 0)
        lcd.write_string(f"Voltage: {voltage:.2f}V")
        print(f"POT: {value}, Voltage: {voltage:.2f}V")
    except Exception as e:
        print(f"Display Error: {e}")

print("Potentiometer test - rotate to see values")
print("Press Ctrl+C to exit")

try:
    # Wait for initial ADC reading
    print("Waiting for valid ADC reading...")
    initial_voltage = None
    
    # Try up to 10 times to get initial reading
    for _ in range(10):
        initial_voltage = read_adc()
        if initial_voltage is not None:
            break
        time.sleep(0.5)
    
    if initial_voltage is None:
        print("WARNING: Could not get initial ADC reading, check your connections")
        initial_voltage = 2.5  # Default if we can't read
    
    # Initial display update
    initial_value = int(initial_voltage * 1023 / 5.0)
    update_display(initial_value, initial_voltage)
    print(f"Initial reading: {initial_value} ({initial_voltage:.2f}V)")
    
    # Main loop
    last_value = initial_value
    consecutive_errors = 0
    while True:
        # Read potentiometer from ADC channel 0
        voltage = read_adc()
        
        if voltage is None:
            consecutive_errors += 1
            if consecutive_errors >= 5:
                print("Multiple consecutive ADC read errors - check your connections")
                consecutive_errors = 0
            time.sleep(0.5)
            continue
        
        consecutive_errors = 0
        
        # Convert voltage (0-5V) to range (0-1023)
        value = int(voltage * 1023 / 5.0)
        
        # Update display if value changed significantly
        if abs(value - last_value) > 5:
            update_display(value, voltage)
            last_value = value
        
        # Short delay
        time.sleep(0.1)
        
except KeyboardInterrupt:
    print("\nTest stopped by user")
except Exception as e:
    print(f"Error: {e}")
finally:
    # Clean up
    try:
        lcd.clear()
        print("Cleanup complete")
    except:
        pass
