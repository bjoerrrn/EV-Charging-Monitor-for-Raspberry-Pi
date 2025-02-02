![stars](https://img.shields.io/github/stars/bjoerrrn/shellrecharge-wallbox-monitor) ![last_commit](https://img.shields.io/github/last-commit/bjoerrrn/shellrecharge-wallbox-monitor)

# Wallbox Monitor  

**A Python script for monitoring a local wallbox charging station from NewMotion / Shell Recharge and sending notifications via Discord.**  

## Features
- Reads charging rate and consumed energy from a web-based wallbox interface.
- Uses **Selenium** to extract data dynamically.
- Sends notifications to **Discord** when charging starts, stops, and after 5 minutes.
- **Prevents false positives** by only detecting charging above **1.0 kW**.
- Stores last state in `/tmp/wallbox_state.txt` to avoid duplicate alerts.
- **Handles missing values gracefully**.

## Setup & Installation  

### **1️⃣ Install Dependencies**
On a **Raspberry Pi**, run:  
```bash
sudo apt update
sudo apt install python3 python3-pip chromium-chromedriver
pip3 install selenium requests
```

### **2️⃣ Clone This Repository**
```bash
git clone https://github.com/bjoerrrn/wallbox-monitor.git
cd wallbox-monitor/
```

### **3️⃣ Configure Your Script**

Open wallbox_monitor.credo and set:
-	Wallbox URL: Change
```bash
WALLBOX_URL = "http://<your-local-wallbox-ip>:12800/user/user.html"
```

-	Discord Webhook: Replace
```bash
DISCORD_WEBHOOK_URL = "<your-discord-webhook-url>"
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
⚡ 02.02.24, 14:35: Charging started.
⚡ Charging power: 3.55 kW
🔋 02.02.24, 15:05: Charging stopped.
⚡ Consumed energy: 3.38 kWh
```

### **📝 Logging**

Check logs in:
```bash
cat /home/pi/wallbox_monitor.log
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
