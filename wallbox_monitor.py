#!/usr/bin/env python3

# v1.2.0
# shellrecharge-wallbox-monitor - by bjoerrrn
# github: https://github.com/bjoerrrn/shellrecharge-wallbox-monitor
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
        return {
            "WALLBOX_URL": config.get("CREDENTIALS", "WALLBOX_URL"),
            "DISCORD_WEBHOOK_URL": config.get("CREDENTIALS", "DISCORD_WEBHOOK_URL"),
            "FIXED_PRICE": float(config.get("CREDENTIALS", "FIXED_PRICE", fallback="0")) or 0
        }
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

def send_discord_notification(message):
    print(f"📢 Sending Discord Notification: {message}")
    payload = {"content": message}
    try:
        requests.post(CONFIG["DISCORD_WEBHOOK_URL"], json=payload, timeout=5)
        logging.info(f"Sent Discord notification: {message}")
    except requests.RequestException as e:
        print(f"Error sending Discord notification: {e}")
        logging.error(f"Error sending Discord notification: {e}")

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
    """Reads the last state and ensures `total_energy_wh_for_summary` is retained persistently."""
    try:
        with open(STATE_FILE, "r") as f:
            data = f.read().strip()

        if data.startswith("charging:"):
            parts = data.split(":")
            if len(parts) >= 5:  # Ensure we get total_energy_wh_for_summary
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
            if len(parts) >= 3:  # Ensure we get total_energy_wh_for_summary
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

        elif data == "disconnected":
            return {
                "state": "disconnected",
                "start_time": None,
                "stored_power": 0.0,
                "total_energy_wh_for_summary": None,  # No energy recorded
                "notified": False,
            }

    except (FileNotFoundError, ValueError, IndexError):
        logging.error("State file corrupted or missing. Resetting to default.")

    # Ensure a valid return structure if parsing fails
    return {
        "state": "idle",
        "start_time": None,
        "stored_power": 0.0,
        "total_energy_wh_for_summary": None,
        "notified": False,
    }

def save_last_state(state, charging_power=0.0, total_energy_wh=None, total_energy_wh_for_summary=None, notified=False):
    """Stores the latest state, ensuring `total_energy_wh_for_summary` is retained persistently until used."""
    with open(STATE_FILE, "w") as f:
        if state == "charging":
            f.write(f"charging:{time.time()}:{charging_power:.2f}:{int(notified)}:{total_energy_wh_for_summary or 0.0}")
        elif state == "idle" and total_energy_wh is not None:
            f.write(f"idle:{total_energy_wh:.2f}:{total_energy_wh_for_summary or 0.0}")  # Preserve total energy & summary
        elif state == "disconnected":
            if total_energy_wh_for_summary is not None:
                f.write(f"disconnected:{total_energy_wh_for_summary:.2f}")  # Store for summary
            else:
                f.write("disconnected")  # Normal case after summary
        else:
            f.write("idle")
            
def send_energy_summary(total_energy_wh_for_summary):
    """Sends a summary of total consumed energy when the cable is disconnected."""
    if total_energy_wh_for_summary is None or total_energy_wh_for_summary <= 0:
        return  # Nothing to summarize

    total_consumed_kwh = total_energy_wh_for_summary / 1000  # Convert Wh → kWh
    price_eur = total_consumed_kwh * CONFIG["FIXED_PRICE"]

    summary_message = f"💶 total: {format_energy(total_energy_wh_for_summary)}" + \
                      (f" = {price_eur:.2f} €" if CONFIG["FIXED_PRICE"] > 0 else "")

    send_discord_notification(summary_message)

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
        send_discord_notification(fatal_message)
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
        logging.info(f".. debug -- Last State: {last_state} / Stored Power: {stored_power} / Notified: {notified}, New Fetch - Charging Rate: {charging_rate}, Total Energy: {total_energy_wh}, Total Energy for Summary: {total_energy_wh_for_summary}")

        # **STORE total_energy_wh_for_summary WHENEVER total_energy_wh IS NOT NONE**
        # required for the summary report after cable disconnection
        if total_energy_wh is not None:
            save_last_state(last_state, total_energy_wh=total_energy_wh, total_energy_wh_for_summary=total_energy_wh)

        # Handle cable disconnection
        if total_energy_wh is None:
            if last_state != "disconnected":
                send_discord_notification(f"🔌 {timestamp}: cable disconnected.")
                
                # Use last known `total_energy_wh_for_summary`
                send_energy_summary(total_energy_wh_for_summary)

                # Set state to disconnected
                save_last_state("disconnected")
            
            return  # Exit early, no further processing needed
            
        # Handle cable connection
        if last_state == "disconnected":
            send_discord_notification(f"🔌 {timestamp}: cable connected.") 
            save_last_state("idle", total_energy_wh=total_energy_wh)

        # Determine new state
        new_state = "idle" if charging_rate < 1.0 else "charging"

        # Handle charging start
        if last_state != "charging" and new_state == "charging":
            send_discord_notification(f"⚡ {timestamp}: charging started.")
            save_last_state(new_state, charging_rate, notified=False)

        # Send charging rate once & update `notified`
        if last_state == "charging" and not notified and charging_rate > 0:
            send_discord_notification(f"⚡ {timestamp}: charging rate {charging_rate} kW")
            save_last_state(new_state, charging_rate, notified=True)

        # Handle charging stop
        if last_state == "charging" and new_state == "idle":
            send_discord_notification(f"🔋 {timestamp}: charging stopped.")
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

                send_discord_notification(message)

    except Exception as e:
        send_discord_notification(f"🚨 ALERT: {e}")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
