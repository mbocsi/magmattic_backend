#!/usr/bin/env python3
import time
from RPLCD.i2c import CharLCD
import smbus2

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
except Exception as e:
    print(f"LCD Error: {e}")
    exit(1)

# Initialize I2C for ADC - using generic I2C access
# This assumes a simple I2C ADC like MCP3008 or similar
# You may need to adjust the address and registers based on your actual ADC
bus = smbus2.SMBus(1)  # Using I2C bus 1
ADC_ADDRESS = 0x48     # Typical address for many I2C ADCs

# Function to read from ADC - modify for your specific ADC
def read_adc(channel):
    try:
        # This is a generic approach - modify for your specific ADC
        # For example, with MCP3008, you'd use a different protocol
        value = bus.read_word_data(ADC_ADDRESS, channel)
        # Adjust the scaling based on your ADC's resolution
        return value * 5.0 / 65535  # Convert to voltage (assuming 16-bit ADC)
    except Exception as e:
        print(f"ADC Read Error: {e}")
        return 2.5  # Default to mid-range on error

# Display the potentiometer value
def update_display(value, voltage):
    lcd.clear()
    lcd.cursor_pos = (0, 0)
    lcd.write_string(f"POT: {value}")
    lcd.cursor_pos = (1, 0)
    lcd.write_string(f"Voltage: {voltage:.2f}V")
    print(f"POT: {value}, Voltage: {voltage:.2f}V")

print("Potentiometer test - rotate to see values")
print("Press Ctrl+C to exit")

try:
    # Get first reading
    initial_voltage = read_adc(0)  # Channel 0
    initial_value = int(initial_voltage * 1023 / 5.0)
    update_display(initial_value, initial_voltage)
    
    # Main loop
    while True:
        # Read potentiometer from ADC channel 0
        voltage = read_adc(0)
        
        # Convert voltage (0-5V) to range (0-1023)
        value = int(voltage * 1023 / 5.0)
        
        # Update display only when value changes
        if abs(value - initial_value) > 5:  # Add small threshold for stability
            update_display(value, voltage)
            initial_value = value
        
        # Short delay
        time.sleep(0.1)
        
except KeyboardInterrupt:
    print("\nTest stopped by user")
except Exception as e:
    print(f"Error: {e}")
finally:
    # Clean up
    lcd.clear()
    print("Cleanup complete")
