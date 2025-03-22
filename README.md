# Magmattic Backend

This is the app that runs on the raspberry pi. The app is broken into "AppComponents", each one in their own folder.

# Instructions for running
## On Raspberry Pi
### 1. Navigate to ```/home/magmattic/Documents/magmattic_backend```
### 2. Run ```source env/bin/activate``` in command line
### 3. (Optional) Do a ```git pull``` for latest version and make sure you are in 'main' branch (```git checkout main```).
### 4. Run ```python main.py``` in command line
## On Local Machine (using virtual components)
### Prerequisites
- Use Python 3.10 or higher
- I recommend using a virtual environment (venv, conda, etc.)
- Install packages:
  - ```pip install -r requirements.txt```
### Configure virtual components
For now, you need to uncomment the virtual components in ```main.py```.
Comment out the lines that instantiate XXXComponent() objects and uncomment the corresponding virtual components VirtualXXXComponent().
#### Example: Configure Virtual ADC if you don't have ESP32
Instantiate a VirtualADCComponent:
```python
# === Initialize ADC controller (PiPlate or Virtual ADC Only! Comment out if using ESP32) ===
adc_sub_queue = asyncio.Queue()
# adc = ADCComponent(pub_queue=app_pub_queue, sub_queue=adc_sub_queue)
adc = VirtualADCComponent(pub_queue=app_pub_queue, sub_queue=adc_sub_queue)
```
Add the adc to the app:
```python
# === Initialize the app ===
components = [ws, calculation, adc]  # added 'adc' to this array 
app = App(*components, pub_queue=app_pub_queue)
```
Register adc data subscriptions by uncommenting:
```python
# Only uncomment this if using PiPlate or Virtual ADC
app.registerSub(["adc/command"], adc_sub_queue)
```
Done! Kinda annoying, but extremely modular/configurable. I will get around to automating configurations.
### Run
After navigating to project directory, installing packages, and configuring virtual components run in command line:
```bash
python main.py
```
# Get IP address
Look for the IPv4 Address after executing one of the following. This will be needed when connecting the dev client.
## Linux/MacOS/RaspOS (Raspberry Pi):
Run in command line: ```ifconfig```
## Windows:
Run in command line: ```ipconfig```