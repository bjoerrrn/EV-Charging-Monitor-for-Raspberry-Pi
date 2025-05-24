![stars](https://img.shields.io/github/stars/bjoerrrn/shellrecharge-wallbox-monitor) ![last_commit](https://img.shields.io/github/last-commit/bjoerrrn/shellrecharge-wallbox-monitor) ![License](https://img.shields.io/badge/License-GPL_3.0-blue.svg) [![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/bjoerrrn)

# EV Charging Monitor for Raspberry Pi

**A Python script for monitoring a local wallbox charging station and sending notifications via Discord, ntfy, or Pushover.**  

Currently supported wallboxes: 
* NewMotion / Shell Recharge [tested with Business Pro 2.1]

If you want to support addind new EV Chargers, [read here](https://github.com/bjoerrrn/EV-Charging-Monitor-for-Raspberry-Pi/blob/main/CONTRIBUTING.md#-adding-support-for-new-wallbox-models) how to. 

## Features
- Reads charging rate and consumed energy from a web-based wallbox interface.
- Uses **Selenium** to extract data dynamically.
- Supported notification channels: Discord, ntfy, Pushover
- Sends notifications when charging starts, stops, and after 5 minutes: charging rate.
- Sends a notification after charging stopped or interrupted, summarizing consumed energy and time.
- If a fixed price per kWh is configured, the energy consumed between cable connected/disconnected will be summarized in Euro.
- Sends a notification when the cable was connected or disconnected. Also handles short-time unavailabilities of the status page to avoid false-positives.
- Typically, wallboxes sometimes consume energy as long as a cable is connected. **Prevents false positives** by only detecting charging rates above **1.0 kW**.

## Setup & Installation  

### **1️⃣ Install Dependencies**
On a **Raspberry Pi**, run:  
```bash
sudo apt update
sudo apt install -y chromium-browser chromium-chromedriver
sudo apt install -y python3-requests python3-selenium python3-bs4 python3-urllib3
```

### **2️⃣ Clone This Repository**
```bash
git clone https://github.com/bjoerrrn/wallbox-monitoring.git
cd wallbox-monitoring/
```

### **3️⃣ Configure Your Script**

wallbox_monitor.credo: This file contains sensitive credentials, hence the .credo extension. 

Open wallbox_monitor.credo and set:
-	Wallbox URL: Change
```
WALLBOX_URL = http://<your-local-wallbox-ip>:12800/user/user.html
```

-	Discord Webhook: Replace
```
DISCORD_WEBHOOK_URL = <your-discord-webhook-url>
```

- and/or ntfy:
```
NTFY_TOPIC = <your_ntfy_topic>
```

- and/or Pushover:
```
PUSHOVER_USER_KEY = <your_pushover_user_key>
PUSHOVER_API_TOKEN = <your_pushover_api_token>
```

### **4️⃣ Run the Script**

Manual Execution
```bash
python3 wallbox_monitor.py
```

Run Every Minute with Crontab
```bash
crontab -e
```

Add the following line at the bottom:
```bash
* * * * * /usr/bin/python3 /home/pi/wallbox-monitor/wallbox_monitor.py
```
Replace /home/pi/wallbox-monitor/ with your actual script path.

Save and exit.

### **📡 Expected Output**

📢 Notifications

```
🔌 02.02.25, 09:50: Cable connected.
⚡ 02.02.25, 22:20: charging started.
⏳ charging power: 3.55 kW
🔋 02.02.25, 23:30: charging stopped.
🔍 consumed: 3.75 kWh of 15.92 kWh in 01:10 h
🔌 02.02.25, 23:50: Cable disconnected.
💶 total: 15.92 kWh = 5.57 €
```

### **📝 Logging**

Check logs in:
```bash
cat /home/pi/wallbox-monitor/wallbox_monitor.log
```

If you want to show additional debug output in wallbox_monitor.log, add `DEBUG_MODE=True` in crontab:
```bash
* * * * * DEBUG_MODE=True /usr/bin/python3 /home/pi/wallbox-monitor/wallbox_monitor.py
```

.. or in your shell to debug manually:
```bash
export DEBUG_MODE=True
./wallbox_monitor.py
```

#### **External Logging Script Support**

You can configure an external script to be executed whenever the charging state changes. The script will receive a JSON payload containing session details.

1️⃣ Edit your 'wallbox_monitor.credo' file

Add the following line with the path to your external script:
```
EXTERNAL_LOG_SCRIPT = /path/to/your/log_script.sh
```

2️⃣ Ensure your script is executable

```bash
chmod +x /path/to/your/log_script.sh
```

3️⃣ JSON Data Format Passed to the Script:

```json
{
    "state": "charging",
    "start_time": "1739959209.48",
    "stored_power": 1.26,
    "total_energy_kWh": 20.0,
    "notified": 1,
    "repeat_check": 0
}
```

5️⃣ Run and Verify

Whenever the script detects a change in the charging state, it will execute log_script.sh, passing the charging data in JSON format.


### **🛠 Troubleshooting**

#### Selenium Fails: “NoSuchDriverException”

Try reinstalling chromedriver:
```bash
sudo apt install --reinstall chromium-chromedriver
```

#### Charging or Consumed Energy Not Detected

Run debug script:
```bash
python3 test_consumed_debug.py
```


### **🤝 Contributing**

Feel free to open issues or pull requests to improve the script! 🚀

if you want to contact me directly, feel free to do so via discord: https://discordapp.com/users/371404709262786561

### ❤️ Support the Project

This project is open-source and maintained in my free time. If you find this script useful and would like to support its further development, bug fixes, and the addition of new wallbox models, any contribution is greatly appreciated!

You can support the project via:

* **[GitHub Sponsors](https://github.com/sponsors/bjoerrrn)**
* **[Buy Me a Coffee](https://www.buymeacoffee.com/bjoerrrn)**

Your support helps cover development costs and motivates me to keep improving the Wallbox Monitor. Thank you!

### **📜 License**

This project is open-source under the [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.en.html) License.
