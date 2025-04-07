import RPi.GPIO as GPIO
import time
from dc_motor import DCMotor

# Use BCM numbering
GPIO.setmode(GPIO.BCM)

# Motor 1: pins 10, 11 (IN1/IN2), 12 (Enable/PWM)
motor1 = DCMotor(pin1=10, pin2=11, enable_pin=12)

# Motor 2: pins 20, 21 (IN1/IN2), 19 (Enable/PWM)
motor2 = DCMotor(pin1=20, pin2=21, enable_pin=19)

try:
    print("M1 Forward with speed: 50%")
    motor1.forward(50)
    time.sleep(5)
    motor1.stop()
    time.sleep(5)

    print("M1 Backwards with speed: 100%")
    motor1.backwards(100)
    time.sleep(5)

    print("M1 Forward with speed: 10%")
    motor1.forward(10)
    time.sleep(5)

    print("M1 Stop")
    motor1.stop()

    print("M2 Forward with speed: 20%")
    motor2.forward(20)
    time.sleep(5)
    motor2.stop()
    time.sleep(5)

    print("M2 Backwards with speed: 40%")
    motor2.backwards(40)
    time.sleep(5)

    print("M2 Forward with speed: 10%")
    motor2.forward(10)
    time.sleep(5)

    print("M2 Stop")
    motor2.stop()

except KeyboardInterrupt:
    print("Keyboard Interrupt")

finally:
    motor1.stop()
    motor2.stop()
    GPIO.cleanup()
