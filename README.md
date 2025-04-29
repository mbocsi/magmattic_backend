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

# Development & Local Testing

## Requirements
- Python 3.10 or higher
- Recommended: virtual environment (venv, conda, etc.)
- Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the App
Use the following command to run the app:

```bash
python main.py [options]
```

## Command Line Options
You can configure which components to run via the following arguments:

- `--dev` : Enables development mode
  - Defaults to `VirtualMotorComponent`, `VirtualADCComponent`, and disables the physical UI (PUI)

- `--adc-mode [none|virtual|piplate]` : Overrides the ADC configuration
- `--motor-mode [virtual|physical]` : Overrides the motor configuration
- `--pui-mode [enable|disable]` : Enables/disables the physical user interface

### Default Behavior
| Mode        | Motor         | ADC             | PUI           |
|-------------|---------------|------------------|-----------------|
| None        | Physical      | None (wireless) | Enabled         |
| `--dev`     | Virtual       | Virtual         | Disabled        |
| With Flags  | As specified  | As specified     | As specified    |

Examples:
```bash
# Run in production mode with all physical components
python main.py

# Run in dev mode with all virtual components
python main.py --dev

# Run with physical motor, virtual ADC, and disable the UI
python main.py --motor-mode physical --adc-mode virtual --pui-mode disable
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

