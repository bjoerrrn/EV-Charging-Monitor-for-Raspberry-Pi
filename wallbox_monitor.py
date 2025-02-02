#!/usr/bin/env python3

import logging
import time
import re
import configparser
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

# Load configuration from credentials file
CONFIG_FILE = "wallbox_monitor.credo"
config = configparser.ConfigParser()
config.read(CONFIG_FILE)

try:
    WALLBOX_URL = config.get("CREDENTIALS", "WALLBOX_URL")
    DISCORD_WEBHOOK_URL = config.get("CREDENTIALS", "DISCORD_WEBHOOK_URL")
except (configparser.NoSectionError, configparser.NoOptionError, FileNotFoundError) as e:
    logging.error(f"Configuration error: {e}")
    raise SystemExit("Error loading credentials. Check 'wallbox_monitor.credo'.")

LOG_FILE = "/home/pi/wallbox_monitor.log"
STATE_FILE = "/tmp/wallbox_state.txt"

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_browser():
    """Starts a headless browser session using Chromium."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service("/usr/lib/chromium-browser/chromedriver")
    return webdriver.Chrome(service=service, options=options)

def fetch_charging_status(driver):
    """Fetch charging rate and consumed energy from the Wallbox."""
    try:
        driver.get(WALLBOX_URL)

        charging_rate = None
        consumed_energy_wh = None

        for _ in range(30):  # Retry for up to 30 seconds
            try:
                charging_text = driver.find_element(By.ID, "chargingRate").get_attribute("value").strip()
                if charging_text:
                    match = re.search(r"([\d.]+)\s*kw", charging_text)
                    if match:
                        charging_rate = float(match.group(1))

                consumed_text = driver.find_element(By.ID, "consumed").get_attribute("value").strip()
                if consumed_text:
                    match = re.search(r"([\d.]+)\s*(wh|kWh)", consumed_text)
                    if match:
                        consumed_energy_wh = float(match.group(1))
                        if "kWh" in consumed_text:
                            consumed_energy_wh *= 1000  # Convert kWh to Wh

                if charging_rate is not None and consumed_energy_wh is not None:
                    break

            except Exception:
                pass  # Retry

            time.sleep(1)

        return charging_rate, consumed_energy_wh

    except Exception as e:
        logging.error(f"Error fetching charging status: {e}")
        return None, None

def send_discord_notification(message):
    """Sends a notification to Discord."""
    import requests
    payload = {"content": message}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        logging.info(f"Sent Discord notification: {message}")
    except requests.RequestException as e:
        logging.error(f"Error sending Discord notification: {e}")

def main():
    """Main execution function to monitor the Wallbox status."""
    driver = get_browser()
    try:
        charging_rate, _ = fetch_charging_status(driver)

        if charging_rate is not None:
            message = f"⚡ Charging Rate: {charging_rate:.2f} kW"
            print(f"📢 Sending Discord Notification: {message}")
            send_discord_notification(message)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
