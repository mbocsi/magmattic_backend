 #Rui Santos & Sara Santos - Random Nerd Tutorials
# Complete project details at https://RandomNerdTutorials.com/raspberry-pi-pico-dc-motor-micropython/

from dcmotor import DCMotor
from machine import Pin, PWM

from time import sleep
import time

frequency = 20000

pin1 = Pin(10, Pin.OUT)
pin2 = Pin(11, Pin.OUT)
enable1 = PWM(Pin(12), frequency)

dc_motor1 = DCMotor(pin1, pin2, enable1)

pin3 = Pin(20, Pin.OUT)
pin4 = Pin(21, Pin.OUT)
enable2 = PWM(Pin(19), frequency)

dc_motor2 = DCMotor(pin3, pin4, enable2)

# Set min duty cycle (15000) and max duty cycle (65535) 
#dc_motor = DCMotor(pin1, pin2, enable, 15000, 65535)

try:
    while True :
         print('M1 Forward with speed: 50%')
         dc_motor1.forward(50)
         sleep(5)
         dc_motor1.stop()
         sleep(5)
         print('M1 Backwards with speed: 100%')
         dc_motor1.backwards(100)
         sleep(5)
         print('M1 Forward with speed: 10%')
         dc_motor1.forward(10)
         sleep(5)
         print('M1 Stop')
         dc_motor1.stop()
         
         print('M2 Forward with speed: 20%')
         dc_motor2.forward(20)
         sleep(5)
         dc_motor2.stop()
         sleep(5)
         print('M2 Backwards with speed: 40%')
         dc_motor2.backwards(40)
         sleep(5)
         print('M2 Forward with speed: 10%')
         dc_motor2.forward(10)
         sleep(5)
         print('M2 Stop')
         dc_motor2.stop()
         led=Pin(1,Pin.OUT) #Creating LED object from pin14 and Set Pin 14 to output
         n=1
         while n < 100000:

              led.value(1) #Set led turn ON
              time.sleep_us(10)
              led.value(0) #Set led turn OFF
              time.sleep_us(10)
              n = n + 1
    
    
except KeyboardInterrupt:
    print('Keyboard Interrupt')
    dc_motor1.stop()
