#!/usr/bin/env python3

# v1.2.0
# wallbox-monitoring - by bjoerrrn
# github: https://github.com/bjoerrrn/wallbox-monitoring
# This script is licensed under GNU GPL version 3.0 or above

import sys
sys.stdout.reconfigure(encoding='utf-8')

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
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from logging.handlers import RotatingFileHandler
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "wallbox_monitor.log")
STATE_FILE = "/tmp/wallbox_state.txt"

# Logging setup
def setup_logging():
    log_handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=0, encoding="utf-8")
    log_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[log_handler])

setup_logging()

def load_config():
    """Loads credentials and configuration from the .credo file."""
    config_path = os.path.join(SCRIPT_DIR, "wallbox_monitor.credo")
    if not os.path.exists(config_path):
        logging.error("Configuration file missing.")
        raise SystemExit("Error: Missing 'wallbox_monitor.credo'.")

    config = configparser.ConfigParser()
    config.read(config_path)

    try:
        cfg = {
            "WALLBOX_URL": config.get("CREDENTIALS", "WALLBOX_URL"),
            "DISCORD_WEBHOOK_URL": config.get("CREDENTIALS", "DISCORD_WEBHOOK_URL", fallback="").strip(),
            "NTFY_TOPIC": config.get("CREDENTIALS", "NTFY_TOPIC", fallback="").strip(),
            "PUSHOVER_USER_KEY": config.get("CREDENTIALS", "PUSHOVER_USER_KEY", fallback="").strip(),
            "PUSHOVER_API_TOKEN": config.get("CREDENTIALS", "PUSHOVER_API_TOKEN", fallback="").strip(),
            "FIXED_PRICE": float(config.get("CREDENTIALS", "FIXED_PRICE", fallback="0")) or 0
        }

        logging.info(f"Loaded configuration: Wallbox URL: {cfg['WALLBOX_URL']}, "
                     f"Discord: {'Enabled' if cfg['DISCORD_WEBHOOK_URL'] else 'Disabled'}, "
                     f"Ntfy: {'Enabled' if cfg['NTFY_TOPIC'] else 'Disabled'}, "
                     f"Pushover: {'Enabled' if cfg['PUSHOVER_USER_KEY'] and cfg['PUSHOVER_API_TOKEN'] else 'Disabled'}, "
                     f"Fixed Price: {cfg['FIXED_PRICE']} €/kWh")

        return cfg
    except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
        logging.error(f"Configuration error: {e}")
        raise SystemExit(f"Error loading credentials: {e}")

CONFIG = load_config()

def get_browser():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service("/usr/bin/chromedriver")
    return webdriver.Chrome(service=service, options=options)

def send_ntfy_notification(message):
    """Sends a notification using ntfy if configured."""
    ntfy_topic = CONFIG["NTFY_TOPIC"]
    if not ntfy_topic:
        return  # Skip if ntfy is not configured

    print(f"📢 Sending NTFY Notification: {message}")
    try:
        requests.post(f"https://ntfy.sh/{ntfy_topic}", data=message.encode("utf-8"), timeout=5)
        logging.info(f"Sent NTFY notification: {message}")
    except requests.RequestException as e:
        print(f"Error sending NTFY notification: {e}")
        logging.error(f"Error sending NTFY notification: {e}")

def send_pushover_notification(message):
    """Sends a notification using Pushover if configured."""
    user_key = CONFIG["PUSHOVER_USER_KEY"]
    api_token = CONFIG["PUSHOVER_API_TOKEN"]
    if not user_key or not api_token:
        return  # Skip if Pushover is not configured

    print(f"📢 Sending Pushover Notification: {message}")
    payload = {
        "token": api_token,
        "user": user_key,
        "message": message
    }
    try:
        requests.post("https://api.pushover.net/1/messages.json", data=payload, timeout=5)
        logging.info(f"Sent Pushover notification: {message}")
    except requests.RequestException as e:
        print(f"Error sending Pushover notification: {e}")
        logging.error(f"Error sending Pushover notification: {e}")

def send_discord_notification(message):
    print(f"📢 Sending Discord Notification: {message}")
    payload = {"content": message}
    try:
        requests.post(CONFIG["DISCORD_WEBHOOK_URL"], json=payload, timeout=5)
        logging.info(f"Sent Discord notification: {message}")
    except requests.RequestException as e:
        print(f"Error sending Discord notification: {e}")
        logging.error(f"Error sending Discord notification: {e}")

def send_notification(message):
    """Sends a notification to all configured services (Discord, ntfy, Pushover)."""
    logging.info(f"📢 Sending notification: {message}")

    send_discord_notification(message)
    send_ntfy_notification(message)
    send_pushover_notification(message)

    logging.info(f"✅ Notification sent successfully: {message}")

def format_energy(wh):
    if wh is None:
        return "0.00 kWh"
    return f"{wh / 1000:.2f} kWh" if wh >= 1000 else f"{wh:.2f} Wh"

def format_duration(seconds):
    minutes = int(seconds // 60)
    hours = minutes // 60
    minutes %= 60
    return f"{hours}:{minutes:02d} h"

def german_timestamp():
    return datetime.now().strftime("%d.%m.%y, %H:%M")

def get_last_state():
    """Reads the last state and ensures `notified` is retained persistently."""
    try:
        with open(STATE_FILE, "r") as f:
            data = f.read().strip()

        if data.startswith("charging:"):
            parts = data.split(":")
            if len(parts) >= 5:
                _, start_time, stored_power, notified, total_energy_wh_for_summary = parts
                return {
                    "state": "charging",
                    "start_time": float(start_time),
                    "stored_power": float(stored_power),
                    "total_energy_wh_for_summary": float(total_energy_wh_for_summary),
                    "notified": bool(int(notified)), 
                }

        elif data.startswith("idle:"):
            parts = data.split(":")
            if len(parts) >= 3:
                _, stored_power, total_energy_wh_for_summary = parts
                return {
                    "state": "idle",
                    "start_time": None,
                    "stored_power": float(stored_power),
                    "total_energy_wh_for_summary": float(total_energy_wh_for_summary),
                    "notified": False, 
                }

        elif data.startswith("disconnected:"):
            parts = data.split(":")
            if len(parts) == 2:
                _, total_energy_wh_for_summary = parts
                return {
                    "state": "disconnected",
                    "start_time": None,
                    "stored_power": 0.0,
                    "total_energy_wh_for_summary": float(total_energy_wh_for_summary),
                    "notified": False,
                }

    except (FileNotFoundError, ValueError, IndexError):
        logging.error("State file corrupted or missing. Resetting to default.")

    return {
        "state": "idle",
        "start_time": None,
        "stored_power": 0.0,
        "total_energy_wh_for_summary": None,
        "notified": False,
    }

def save_last_state(state, charging_power=0.0, total_energy_wh=None, total_energy_wh_for_summary=None, notified=False):
    """Stores the latest state, ensuring `notified` is retained persistently."""
    with open(STATE_FILE, "w") as f:
        if state == "charging":
            f.write(f"charging:{time.time()}:{charging_power:.2f}:{int(notified)}:{total_energy_wh_for_summary or 0.0}")
        elif state == "idle" and total_energy_wh is not None:
            f.write(f"idle:{total_energy_wh:.2f}:{total_energy_wh_for_summary or 0.0}:{int(notified)}")  
        elif state == "disconnected":
            if total_energy_wh_for_summary is not None:
                f.write(f"disconnected:{total_energy_wh_for_summary:.2f}:{int(notified)}")  
            else:
                f.write("disconnected")
        else:
            f.write(f"idle:0.0:0.0:{int(notified)}")  
            
def send_energy_summary(total_energy_wh_for_summary):
    """Sends a summary of total consumed energy when the cable is disconnected."""
    if total_energy_wh_for_summary is None or total_energy_wh_for_summary <= 0:
        logging.info("Skipping energy summary (no energy recorded).")
        return  # Nothing to summarize

    total_consumed_kwh = total_energy_wh_for_summary / 1000  # Convert Wh → kWh
    price_eur = total_consumed_kwh * CONFIG["FIXED_PRICE"]

    summary_message = f"💶 total: {format_energy(total_energy_wh_for_summary)}" + \
                      (f" = {price_eur:.2f} €" if CONFIG["FIXED_PRICE"] > 0 else "")

    logging.info(f"📢 Sending energy summary: {summary_message}")

    send_notification(summary_message)
    
    logging.info("✅ Energy summary sent. Resetting stored energy summary.")

    # Reset `total_energy_wh_for_summary` after reporting to avoid reuse
    save_last_state("disconnected", total_energy_wh_for_summary=None)

def fetch_charging_status(driver):
    """Fetches charging rate and total energy from the charger."""
    try:
        driver.get(CONFIG["WALLBOX_URL"])
        charging_rate = None
        total_energy_wh = None
        last_exception = None

        # Retry every second for up to 30 seconds
        for attempt in range(10):
            try:
                charging_element = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.ID, "chargingRate"))
                )
                charging_text = charging_element.get_attribute("value").strip()
                if charging_text:
                    match_charging = re.search(r"([\d.]+)\s*kw", charging_text)
                    if match_charging:
                        charging_rate = float(match_charging.group(1))

                try:
                    consumed_element = WebDriverWait(driver, 2).until(
                        EC.presence_of_element_located((By.ID, "consumed"))
                    )
                    consumed_text = consumed_element.get_attribute("value").strip()
                    if consumed_text:
                        match_consumed = re.search(r"([\d.]+)\s*(wh|kWh)", consumed_text)
                        if match_consumed:
                            total_energy_wh = float(match_consumed.group(1))
                            if "kWh" in consumed_text:
                                total_energy_wh *= 1000  # Convert kWh to Wh
                except TimeoutException:
                    total_energy_wh = None  # Energy data unavailable (cable unplugged)

                # Exit loop early if both values are found
                if charging_rate is not None and total_energy_wh is not None:
                    break

            except (NoSuchElementException, TimeoutException) as e:
                last_exception = e  # Store last error for later reporting
                logging.warning(f"Attempt {attempt + 1}: Element not found or timeout - {e}")

            except Exception as e:
                last_exception = e
                logging.error(f"Attempt {attempt + 1}: Unexpected error - {e}")

            time.sleep(1)  # Wait before retrying

        logging.info(f"🔄 Fetched Status - Charging Rate: {charging_rate} kW, Total Energy: {format_energy(total_energy_wh)}")

        return charging_rate, total_energy_wh

    except Exception as e:
        fatal_message = f"🚨 ALERT: {e}"
        logging.critical(fatal_message)
        send_notification(fatal_message)
        return None, None

def main():
    driver = get_browser()

    try:
        charging_rate, total_energy_wh = fetch_charging_status(driver)

        state_data = get_last_state()
        last_state = state_data["state"]
        start_time = state_data["start_time"]
        stored_power = state_data["stored_power"]
        total_energy_wh_for_summary = state_data["total_energy_wh_for_summary"]
        notified = state_data["notified"]

        timestamp = german_timestamp()
        current_time = time.time()

        print(f"🔄 Last State: {last_state}, New Fetch: {charging_rate}, Total Energy: {total_energy_wh}")
        logging.info(f".. debug -- Last State: {last_state} / Stored Power: {stored_power} / Notified: {notified}, "
                     f"New Fetch - Charging Rate: {charging_rate}, Total Energy: {total_energy_wh}, "
                     f"Total Energy for Summary: {total_energy_wh_for_summary}")

        # Handle cable disconnection
        if total_energy_wh is None:
            if last_state != "disconnected":
                send_notification(f"🔌 {timestamp}: cable disconnected.")
                
                # Use last known `total_energy_wh_for_summary`
                send_energy_summary(total_energy_wh_for_summary)

                # Set state to disconnected
                save_last_state("disconnected")
            
            return  # Exit early, no further processing needed
            
        # Handle cable connection
        if last_state == "disconnected":
            send_notification(f"🔌 {timestamp}: cable connected.") 
            save_last_state("idle", total_energy_wh=total_energy_wh)

        # Determine new state
        new_state = "idle" if charging_rate < 1.0 else "charging"

        # **STORE total_energy_wh_for_summary WHENEVER total_energy_wh IS NOT NONE**
        # required for the summary report after cable disconnection
        if total_energy_wh is not None:
            save_last_state(new_state, charging_power=charging_rate, total_energy_wh=total_energy_wh, total_energy_wh_for_summary=total_energy_wh_for_summary, notified=notified)

        # Handle charging start
        if last_state != "charging" and new_state == "charging":
            send_notification(f"⚡ {timestamp}: charging started.")
            save_last_state(new_state, charging_rate, notified=False)

        # notify once per session about charging rate
        if last_state == "charging" and not notified and charging_rate > 0:
            send_notification(f"⚡ {timestamp}: charging rate {charging_rate} kW")
            save_last_state(new_state, charging_power=charging_rate, total_energy_wh=total_energy_wh, total_energy_wh_for_summary=total_energy_wh_for_summary, notified=True)

        # Handle charging stop
        if last_state == "charging" and new_state == "idle":
            send_notification(f"🔋 {timestamp}: charging stopped.")
            save_last_state(new_state, total_energy_wh)

            if total_energy_wh is not None:
                elapsed_time = max(current_time - start_time, 60) if start_time else 60  # Ensure at least 1 minute
                elapsed_formatted = format_duration(elapsed_time)
                
                previous_stored_power = stored_power or total_energy_wh or 0
                session_energy_wh = max(total_energy_wh - previous_stored_power, 0)

                if format_energy(session_energy_wh) == format_energy(total_energy_wh):
                    message = f"🔍 {format_energy(session_energy_wh)} in {elapsed_formatted}"
                else:
                    message = f"🔍 {format_energy(session_energy_wh)} of {format_energy(total_energy_wh)} in {elapsed_formatted}"

                send_notification(message)

    except Exception as e:
        send_notification(f"🚨 ALERT: {e}")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
