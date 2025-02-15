![stars](https://img.shields.io/github/stars/bjoerrrn/shellrecharge-wallbox-monitor) ![last_commit](https://img.shields.io/github/last-commit/bjoerrrn/shellrecharge-wallbox-monitor)

# Wallbox Monitor  

**A Python script for monitoring a local wallbox charging station from NewMotion / Shell Recharge and sending notifications via Discord.**  

## Features
- Reads charging rate and consumed energy from a web-based wallbox interface.
- Uses **Selenium** to extract data dynamically.
- Supported notification channels: Discord, ntfy, Pushover
- Sends notifications when charging starts, stops, and after 5 minutes: charging rate.
- Sends a notification after charging stopped, summarizing consumed energy and time.
- If a fixed price per kWh is configured, the energy consumed between cable connected/disconnected will be summarized in Euro.
- Sends a notification when the cable was connected or disconnected.
- **Prevents false positives** by only detecting charging above **1.0 kW**.
- **Handles missing values gracefully**.

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
git clone https://github.com/bjoerrrn/wallbox-monitor.git
cd wallbox-monitor/
```

### **3️⃣ Configure Your Script**

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

Save and exit.

### **📡 Expected Output**

📢 Discord Notifications
```
🔌 02.02.25, 21:50: Cable connected.
⚡ 02.02.25, 22:20: charging started.
⏳ charging power: 2.30 kW
🔋 02.02.25, 22:30: charging stopped.
🔍 consumed: 1.25 kWh in 00:10 h
🔌 02.02.25, 23:50: Cable disconnected.
💶 total: 1.25 kWh = 0.44 €
```

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

### **🛠 Troubleshooting**

Selenium Fails: “NoSuchDriverException”

Try reinstalling chromedriver:
```bash
sudo apt install --reinstall chromium-chromedriver
```

Charging or Consumed Energy Not Detected

Run debug script:
```bash
python3 test_consumed_debug.py
```

### **🤝 Contributing**

Feel free to open issues or pull requests to improve the script! 🚀

if you want to contact me directly, feel free to do so via discord: https://discordapp.com/users/371404709262786561

### **📜 License**

This project is open-source under the [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.en.html) License.
