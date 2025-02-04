#!/usr/bin/env python3

# v1.0.5
# shellrecharge-wallbox-monitor - by bjoerrrn
# github: https://github.com/bjoerrrn/shellrecharge-wallbox-monitor
# This script is licensed under GNU GPL version 3.0 or above

import os
import logging
import time
import re
import configparser
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from logging.handlers import RotatingFileHandler
import requests

# Get script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Logging configuration with rotation
LOG_FILE = os.path.join(SCRIPT_DIR, "wallbox_monitor.log")
log_handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=0)
log_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[log_handler])

# Load configuration file
CONFIG_FILE = os.path.join(SCRIPT_DIR, "wallbox_monitor.credo")
config = configparser.ConfigParser()

if not os.path.exists(CONFIG_FILE):
    logging.error("Configuration file missing. Ensure 'wallbox_monitor.credo' exists.")
    print("Error: Missing 'wallbox_monitor.credo'.")
    raise SystemExit("Error: Missing 'wallbox_monitor.credo'.")

try:
    config.read(CONFIG_FILE)
    WALLBOX_URL = config.get("CREDENTIALS", "WALLBOX_URL")
    DISCORD_WEBHOOK_URL = config.get("CREDENTIALS", "DISCORD_WEBHOOK_URL")
except (configparser.NoSectionError, configparser.NoOptionError) as e:
    logging.error(f"Configuration error: {e}")
    print(f"Error loading credentials: {e}")
    raise SystemExit("Error loading credentials. Check 'wallbox_monitor.credo'.")

STATE_FILE = "/tmp/wallbox_state.txt"

def get_browser():
    """Starts a headless browser session using Chromium."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service("/usr/lib/chromium-browser/chromedriver")
    return webdriver.Chrome(service=service, options=options)

def fetch_charging_status(driver):
    """Uses Selenium to get the dynamically updated charging rate and consumed energy."""
    try:
        driver.get(WALLBOX_URL)

        charging_rate = None
        total_energy_wh = None

        # Wait up to 30 seconds for both values to be populated
        for _ in range(30):  # Retry every second for up to 30 seconds
            try:
                # Get charging rate
                charging_element = driver.find_element(By.ID, "chargingRate")
                charging_text = charging_element.get_attribute("value").strip()
                if charging_text:
                    match_charging = re.search(r"([\d.]+)\s*kw", charging_text)
                    if match_charging:
                        charging_rate = float(match_charging.group(1))

                # Get consumed energy
                consumed_element = driver.find_element(By.ID, "consumed")
                consumed_text = consumed_element.get_attribute("value").strip()
                if consumed_text:
                    match_consumed = re.search(r"([\d.]+)\s*(wh|kWh)", consumed_text)
                    if match_consumed:
                        total_energy_wh = float(match_consumed.group(1))
                        if "kWh" in consumed_text:
                            total_energy_wh *= 1000  # Convert kWh to Wh

                # Exit loop early if both values are found
                if charging_rate is not None and total_energy_wh is not None:
                    break

            except Exception:
                pass  # Ignore errors and retry

            time.sleep(1)  # Wait 1 second before retrying

        return charging_rate, total_energy_wh

    except Exception as e:
        logging.error(f"Error fetching charging status: {e}")
        print(f"Error fetching charging status: {e}")
        return None, None


def format_energy(wh):
    """Converts Wh to kWh if necessary and formats output with two decimal places."""
    if wh is None:
        return "0.00 kWh"
    return f"{wh / 1000:.2f} kWh" if wh >= 1000 else f"{wh:.2f} Wh"
    
def format_duration(seconds):
    """Formats seconds into hours and minutes, e.g., hh:mm."""
    minutes = int(seconds // 60)
    hours = minutes // 60
    minutes %= 60
    return f"{hours}:{minutes:02d} h"

def german_timestamp():
    """Returns the current time in German short format: DD.MM.YY, HH:MM."""
    return datetime.now().strftime("%d.%m.%y, %H:%M")

def send_discord_notification(message):
    """Sends a notification to Discord."""
    payload = {"content": message}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        logging.info(f"Sent Discord notification: {message}")
        print(f"Sent Discord notification: {message}")
    except requests.RequestException as e:
        logging.error(f"Error sending Discord notification: {e}")
        print(f"Error sending Discord notification: {e}")
        
def get_last_state():
    """Reads the last state, charging start time, power, and notified flag from the state file."""
    try:
        with open(STATE_FILE, "r") as f:
            data = f.read().strip()
            if data.startswith("charging:"):
                parts = data.split(":")
                try:
                    timestamp = float(parts[1]) if parts[1] != "None" else 0.0
                    power = float(parts[2]) if parts[2] != "None" else 0.0
                    notified = parts[3] == "1" if len(parts) > 3 else False
                    return "charging", timestamp, power, notified
                except ValueError as e:
                    logging.error(f"Value Error: {e}")
                    print(f"Value Error: {e}")
                    return "idle", None, None, False
            return data, None, None, False
    except FileNotFoundError as e:
        with open(STATE_FILE, "w") as f:
            f.write("idle")
        return "idle", None, None, False
            
def save_last_state(state, charging_power=0.0, notified=False):
    """Saves the current state, timestamp, power, and notified flag."""
    with open(STATE_FILE, "w") as f:
        if state == "charging":
            charging_power = charging_power if charging_power is not None else 0.0  # Ensure valid number
            f.write(f"charging:{time.time()}:{charging_power:.2f}:{int(notified)}") # Store timestamp + power + notified
        else:
            f.write("idle")  # Reset if charging stops

def main():
    """Checks wallbox status and triggers notifications when state changes."""
    driver = get_browser()

    try:
        charging_rate, total_energy_wh = fetch_charging_status(driver)

        print(f"🔍 Charging Rate: {charging_rate}, Consumed Energy: {total_energy_wh}")
        logging.info(f"🔍 Charging Rate: {charging_rate}, Consumed Energy: {total_energy_wh}")

        if charging_rate is not None:
            new_state = "charging" if charging_rate >= 1.0 else "idle"
            last_state, start_time, stored_power, notified = get_last_state()

            timestamp = german_timestamp()
            current_time = time.time()

            print(f"🔄 Last State: {last_state}, New State: {new_state}")
            logging.info(f"🔄 Last State: {last_state}, New State: {new_state}")

            if last_state != new_state:  # Only trigger on state change
                if new_state == "charging":
                    message = f"⚡ {timestamp}: charging started."
                    print(f"📢 Sending Discord Notification: {message}")
                    logging.info(f"📢 Sending Discord Notification: {message}")
                    send_discord_notification(message)
                    save_last_state(new_state, charging_rate, notified=False)  # Store start time & power
                else:
                    message = f"🔋 {timestamp}: charging stopped."
                    print(f"📢 Sending Discord Notification: {message}")
                    logging.info(f"📢 Sending Discord Notification: {message}")
                    send_discord_notification(message)
                    save_last_state(new_state)  # Reset state

            # If charging, check if 5 minutes have passed
            elif new_state == "charging" and start_time is not None and not notified:
                elapsed_time = current_time - start_time if start_time else 0
                print(f"⏳ Elapsed Charging Time: {elapsed_time:.2f} seconds")
                logging.info(f"⏳ Elapsed Charging Time: {elapsed_time:.2f} seconds")

                if elapsed_time >= 300:  # 300 seconds = 5 minutes
                    latest_charging_rate, _ = fetch_charging_status(driver)  # Fetch latest power
                    message = f"⏳ charging power: {latest_charging_rate:.2f} kW"
                    print(f"📢 Sending Discord Notification: {message}")
                    logging.info(f"📢 Sending Discord Notification: {message}")
                    send_discord_notification(message)
                    save_last_state("charging", latest_charging_rate, notified=True)
                    
            # If charging stopped, send a separate consumption message
            if last_state == "charging" and new_state == "idle" and total_energy_wh is not None:
                elapsed_time = current_time - start_time if start_time else 0
                elapsed_formatted = format_duration(elapsed_time)
                session_energy_wh = total_energy_wh - stored_power if stored_power is not None else total_energy_wh
                
                if stored_power == 0 or session_energy_wh == stored_power:
                    message = f"🔍 consumed: {format_energy(session_energy_wh)} in  {elapsed_formatted}"
                else:
                    message = f"🔍 consumed: {format_energy(session_energy_wh)} of {format_energy(total_energy_wh)} in {elapsed_formatted}"
                
                print(f"📢 Sending Discord Notification: {message}")
                logging.info(f"📢 Sending Discord Notification: {message}")
                send_discord_notification(message)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
