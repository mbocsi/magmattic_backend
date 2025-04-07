#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time

# Clean up any existing GPIO setup
try:
    GPIO.cleanup()
except:
    pass

# Set up GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Mode button
GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Power button

print("Button test running - press buttons (Ctrl+C to exit)")
print("Button 17 (MODE) and Button 22 (POWER) will be detected")

try:
    # Track previous states for edge detection
    prev_state_17 = GPIO.input(17)
    prev_state_22 = GPIO.input(22)
    
    while True:
        # Read current states
        state_17 = GPIO.input(17)
        state_22 = GPIO.input(22)
        
        # Check for button press (HIGH to LOW transition with pull-up)
        if prev_state_17 == GPIO.HIGH and state_17 == GPIO.LOW:
            print("BUTTON 17 (MODE) PRESSED!")
            
        if prev_state_22 == GPIO.HIGH and state_22 == GPIO.LOW:
            print("BUTTON 22 (POWER) PRESSED!")
        
        # Print raw states periodically
        if int(time.time()) % 5 == 0:
            print(f"Raw states - B17: {state_17}, B22: {state_22}")
            time.sleep(1)  # Avoid repeated printing
            
        # Update previous states
        prev_state_17 = state_17
        prev_state_22 = state_22
        
        # Short delay
        time.sleep(0.05)
        
except KeyboardInterrupt:
    print("\nButton test stopped by user")
finally:
    GPIO.cleanup()
    print("GPIO cleaned up")
