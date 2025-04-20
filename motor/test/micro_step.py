import RPi.GPIO as GPIO  # type: ignore
import time

LED_PIN = 13  # GPIO1 (BCM numbering) – double-check your wiring!

GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

pwm = GPIO.PWM(LED_PIN, 1600)

try:
    pwm.start(50)  # 50% duty cycle → 10us ON, 10us OFF

    # Run indefinitely (or you could use time.sleep(duration))
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("Keyboard Interrupt")

finally:
    pwm.stop()
    GPIO.cleanup()
