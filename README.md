# Magmattic Backend

This is the app that runs on the raspberry pi. The app is broken into "AppComponents", each one in their own folder.

# Instructions for running
## Prerequisites
- Use Python 3.10 or higher
- Install packages:
  - ```pip install -r requirements.txt```
## Configure
### For virtual/local use:
Main.py is configured to use virtual components by default. 
### For use with Raspberry pi:
Comment out the lines that instantiate VirtualXXXComponent() objects and uncomment the corresponding real components (XXXComponent()) for each piece of hardware that is connected. Ex:
```
adc = ADCComponent() # Uncomment this
# adc = VirtualADCComponent() # Comment this out
```
## Get IP address
Look for the IPv4 Address after executing one of the following
### Linux/MacOS/RaspOS (Raspberry Pi):
Run in command line: ```ifconfig```
### Windows:
Run in command line: ```ipconfig```
## Run
```python main.py```