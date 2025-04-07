import RPi.GPIO as GPIO


class DCMotor:
    def __init__(self, pin1, pin2, enable_pin, min_duty=20, max_duty=100):
        self.pin1 = pin1
        self.pin2 = pin2
        self.enable = enable_pin
        self.min_duty = min_duty
        self.max_duty = max_duty

        GPIO.setup(self.pin1, GPIO.OUT)
        GPIO.setup(self.pin2, GPIO.OUT)
        GPIO.setup(self.enable, GPIO.OUT)

        self.pwm = GPIO.PWM(self.enable, 20000)  # 20 kHz
        self.pwm.start(0)

    def forward(self, speed):
        GPIO.output(self.pin1, GPIO.HIGH)
        GPIO.output(self.pin2, GPIO.LOW)
        self.pwm.ChangeDutyCycle(self._duty_cycle(speed))

    def backwards(self, speed):
        GPIO.output(self.pin1, GPIO.LOW)
        GPIO.output(self.pin2, GPIO.HIGH)
        self.pwm.ChangeDutyCycle(self._duty_cycle(speed))

    def stop(self):
        GPIO.output(self.pin1, GPIO.LOW)
        GPIO.output(self.pin2, GPIO.LOW)
        self.pwm.ChangeDutyCycle(0)

    def _duty_cycle(self, speed):
        if speed <= 0 or speed > 100:
            return 0
        return self.min_duty + (self.max_duty - self.min_duty) * (speed / 100)
