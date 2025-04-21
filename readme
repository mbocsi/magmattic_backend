# Magmattic Backend

This is the app that runs on the Raspberry Pi. The app is broken into modular "AppComponents", each in their own folder.

---

# ✅ Current Raspberry Pi Setup (Automatic)

As of the latest setup, **you do not need to manually start the backend**.

When the Raspberry Pi boots:
- The backend app is **automatically updated** if connected to the internet (pulls the latest version from the `main` branch).
- The app is executed as a **systemd service**.
- A **Wi-Fi hotspot** is started with the following credentials:
  - SSID: `Magpi`
  - Password: `magmattic2025`
- If connected to the Pi’s hotspot, the Pi is accessible at:  
  `http://magpi.local`

---

# Legacy Instructions (for development / local testing)

## On Local Machine (using virtual components)

### Prerequisites
- Python 3.10 or higher
- Recommended: virtual environment (venv, conda, etc.)
- Install dependencies:
```bash
pip install -r requirements.txt
```

### Configure Virtual Components

To use virtual components for local testing, edit `main.py`:
- Comment out real hardware component instances (`XXXComponent`)
- Uncomment the corresponding `VirtualXXXComponent`

#### Example: Use Virtual ADC
```python
# === Initialize ADC controller (PiPlate or Virtual ADC Only! Comment out if using ESP32) ===
adc_sub_queue = asyncio.Queue()
# adc = ADCComponent(pub_queue=app_pub_queue, sub_queue=adc_sub_queue)
adc = VirtualADCComponent(pub_queue=app_pub_queue, sub_queue=adc_sub_queue)
```

Add the ADC to the app:
```python
components = [ws, calculation, adc]
app = App(*components, pub_queue=app_pub_queue)
```

Register subscriptions:
```python
app.registerSub(["adc/command"], adc_sub_queue)
```

### Run Locally
After setup:
```bash
python main.py
```

---

# Networking / IP Info

If you are not using `magpi.local`, you can still find the Pi's IP address.

## Linux/MacOS/RaspOS:
```bash
ifconfig
```

## Windows:
```bash
ipconfig
```

