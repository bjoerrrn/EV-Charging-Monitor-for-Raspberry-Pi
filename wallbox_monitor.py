#!/usr/bin/env python3

# v1.2.2
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

DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"

# Logging setup
def setup_logging():
    global logger  # Make logger accessible globally
    logger = logging.getLogger()  # Get the root logger

    log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # Create a file handler
    file_handler = logging.FileHandler(LOG_FILE, mode="a")
    file_handler.setFormatter(log_formatter)

    # Create a stream handler (for debugging)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)

    logger.setLevel(logging.INFO)  # Set log level to INFO
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)  # Also print logs to the console

setup_logging()

def debug(message):
    """Logs additional info messages, when DEBUG_MODE=true."""
    if DEBUG_MODE: 
        logger.info(message)

def load_config():
    """Loads credentials and configuration from the .credo file."""
    config_path = os.path.join(SCRIPT_DIR, "wallbox_monitor.credo")
    if not os.path.exists(config_path):
        logger.error("Configuration file missing.")
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

        debug(f"Loaded configuration: Wallbox URL: {cfg['WALLBOX_URL']}, "
             f"Discord: {'Enabled' if cfg['DISCORD_WEBHOOK_URL'] else 'Disabled'}, "
             f"Ntfy: {'Enabled' if cfg['NTFY_TOPIC'] else 'Disabled'}, "
             f"Pushover: {'Enabled' if cfg['PUSHOVER_USER_KEY'] and cfg['PUSHOVER_API_TOKEN'] else 'Disabled'}, "
             f"Fixed Price: {cfg['FIXED_PRICE']} €/kWh")

        return cfg
    except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
        logger.error(f"Configuration error: {e}")
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
        debug(f"Sent NTFY notification: {message}")
    except requests.RequestException as e:
        print(f"Error sending NTFY notification: {e}")
        logger.error(f"Error sending NTFY notification: {e}")

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
        "message": message,
        "ttl": 43200
    }
    try:
        requests.post("https://api.pushover.net/1/messages.json", data=payload, timeout=5)
        debug(f"Sent Pushover notification: {message}")
    except requests.RequestException as e:
        print(f"Error sending Pushover notification: {e}")
        logger.error(f"Error sending Pushover notification: {e}")

def send_discord_notification(message):
    print(f"📢 Sending Discord Notification: {message}")
    payload = {"content": message}
    try:
        requests.post(CONFIG["DISCORD_WEBHOOK_URL"], json=payload, timeout=5)
        debug(f"Sent Discord notification: {message}")
    except requests.RequestException as e:
        print(f"Error sending Discord notification: {e}")
        logger.error(f"Error sending Discord notification: {e}")

def send_notification(message):
    """Sends a notification to all configured services, skipping disabled ones."""
    debug(f"📢 Sending notification: {message}")

    if CONFIG["DISCORD_WEBHOOK_URL"]:
        send_discord_notification(message)
    
    if CONFIG["NTFY_TOPIC"]:
        send_ntfy_notification(message)
    
    if CONFIG["PUSHOVER_USER_KEY"] and CONFIG["PUSHOVER_API_TOKEN"]:
        send_pushover_notification(message)

    logger.info(f"✅ Notification sent successfully: {message}")

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
    try:
        with open(STATE_FILE, "r") as f:
            data = f.read().strip()

        if data.startswith("charging:") or data.startswith("idle:"):
            parts = data.split(":")
            if len(parts) >= 6:
                _, start_time, stored_power, notified, total_energy_wh_for_summary, repeat_check = parts
                return {
                    "state": "charging" if data.startswith("charging:") else "idle",
                    "start_time": float(start_time) if data.startswith("charging:") else None,
                    "stored_power": float(stored_power),
                    "total_energy_wh_for_summary": float(total_energy_wh_for_summary),
                    "notified": bool(int(notified)),
                    "repeat_check": bool(int(repeat_check)),  # NEW FLAG
                }

        elif data.startswith("disconnected:"):
            parts = data.split(":")
            if len(parts) >= 4:
                _, total_energy_wh_for_summary, notified, repeat_check = parts
                return {
                    "state": "disconnected",
                    "start_time": None,
                    "stored_power": 0.0,
                    "total_energy_wh_for_summary": float(total_energy_wh_for_summary),
                    "notified": bool(int(notified)),
                    "repeat_check": bool(int(repeat_check)),  # NEW FLAG
                }

    except (FileNotFoundError, ValueError, IndexError):
        logger.error("State file corrupted or missing. Resetting to default.")
        logger.error(f"State file content: {data}")  # Debugging

    return {
        "state": "idle",
        "start_time": None,
        "stored_power": 0.0,
        "total_energy_wh_for_summary": 0.0,
        "notified": False,
        "repeat_check": False,
    }

def save_last_state(state, stored_power=0.0, total_energy_wh_for_summary=0.0, notified=False, start_time=None, repeat_check=False):
    with open(STATE_FILE, "w") as f:
        if state in ["charging", "idle"]:
            start_time_str = str(start_time) if state == "charging" and start_time is not None else "0"
            f.write(f"{state}:{start_time_str}:{stored_power:.2f}:{int(notified)}:{total_energy_wh_for_summary or 0.0}:{int(repeat_check)}")
            debug(f".. save_last_state(): {state}:{start_time_str}:{stored_power:.2f}:{int(notified)}:{total_energy_wh_for_summary or 0.0}:{int(repeat_check)}")

        elif state == "disconnected":
            f.write(f"disconnected:{total_energy_wh_for_summary if total_energy_wh_for_summary is not None else '0.0'}:{int(notified)}:{int(repeat_check)}")
            debug(f".. save_last_state(): disconnected:{total_energy_wh_for_summary if total_energy_wh_for_summary is not None else '0.0'}:{int(notified)}:{int(repeat_check)}")

        else:
            f.write(f"idle:0.0:0.0:{int(notified)}:{int(repeat_check)}")
            debug(f".. save_last_state(): idle:0.0:0.0:{int(notified)}:{int(repeat_check)}")
            
def send_energy_summary(total_energy_wh_for_summary):
    """Sends a summary of total consumed energy when the cable is disconnected."""
    if total_energy_wh_for_summary is None or total_energy_wh_for_summary <= 0:
        debug("Skipping energy summary (no energy recorded).")
        return  # Nothing to summarize

    total_consumed_kwh = total_energy_wh_for_summary / 1000  # Convert Wh → kWh
    price_eur = total_consumed_kwh * CONFIG["FIXED_PRICE"]

    summary_message = f"💶 total: {format_energy(total_energy_wh_for_summary)}" + \
                      (f" = {price_eur:.2f} €" if CONFIG["FIXED_PRICE"] > 0 else "")

    debug(f"📢 Sending energy summary: {summary_message}")
    send_notification(summary_message)
    logger.info("✅ Energy summary sent. Resetting stored energy summary.")

    # Reset `total_energy_wh_for_summary` after reporting to avoid reuse
    save_last_state("disconnected", total_energy_wh_for_summary=0)

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
                logger.warning(f"Attempt {attempt + 1}: Element not found or timeout - {e}")

            except Exception as e:
                last_exception = e
                logger.error(f"Attempt {attempt + 1}: Unexpected error - {e}")

            time.sleep(1)  # Wait before retrying

        debug(f"🔄 Fetched Status - Charging Rate: {charging_rate} kW, Total Energy: {format_energy(total_energy_wh)}")

        if charging_rate is None:
            logger.warning("⚠️ Warning: charging_rate is None. Setting to 0.0.")
        return charging_rate if charging_rate is not None else 0.0, total_energy_wh

    except Exception as e:
        fatal_message = f"🚨 ALERT (fetch): {e}"
        logger.critical(fatal_message)
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
        repeat_check = state_data["repeat_check"]  # NEW FLAG
        
        if total_energy_wh is None:
            total_energy_wh = get_last_state().get("total_energy_wh") 

        timestamp = german_timestamp()
        current_time = time.time()

        print(f"🔄 Last State: {last_state}, New Fetch: {charging_rate}, Total Energy: {total_energy_wh}")
        debug(f".. get_last_state() #1 \n-- state file: \n   Last State: {last_state} \n   Start Time: {start_time} \n   Stored Power: {stored_power} \n   Total Energy for Summary: {total_energy_wh_for_summary} \n   Notified: {notified} \n   Repeat Check: {repeat_check} \n-- new fetch: \n   Charging Rate: {charging_rate} \n   Total Energy: {total_energy_wh}")
        
        # 🚨 If disconnect detected DURING charging, set repeat_check and exit
        if last_state == "charging" and (total_energy_wh is None or charging_rate == 0):
            if not repeat_check:  # First detection, re-run once
                debug(f"🔌 {timestamp}: charging interruption detected, verifying...")
                save_last_state("charging", stored_power=stored_power, total_energy_wh_for_summary=total_energy_wh_for_summary, notified=notified, start_time=start_time, repeat_check=True)
                return  # Exit, script will retry next run

            # Second run, confirmed interruption
            send_notification(f"🔌 {timestamp}: charging interrupted - cable unplugged.")
            send_energy_summary(total_energy_wh_for_summary)
            save_last_state("disconnected", total_energy_wh_for_summary=total_energy_wh_for_summary, repeat_check=False)  # Reset repeat_check
            return  # Exit after confirming

        # 🚨 If normal disconnect detected (idle state), set repeat_check and exit
        if total_energy_wh is None and last_state == "idle":
            if not repeat_check:  # First detection, re-run once
                debug(f"🔌 {timestamp}: cable disconnect detected, verifying...")
                save_last_state("idle", stored_power=stored_power, total_energy_wh_for_summary=total_energy_wh_for_summary, notified=notified, repeat_check=True)
                return  # Exit, script will retry next run

            # Second run, confirmed disconnection
            send_notification(f"🔌 {timestamp}: cable disconnected.")
            send_energy_summary(total_energy_wh_for_summary)
            save_last_state("disconnected", total_energy_wh_for_summary=total_energy_wh_for_summary, repeat_check=False)  # Reset repeat_check
            return  # Exit after confirming

        # 🚀 Handle cable reconnection
        if last_state == "disconnected" and total_energy_wh is not None:
            send_notification(f"🔌 {timestamp}: cable connected.") 
            save_last_state("idle", stored_power=stored_power, repeat_check=False)

        # 🔋 Determine new state
        new_state = "idle" if not isinstance(charging_rate, (int, float)) or charging_rate < 1.0 else "charging"

        # 📌 Store latest total energy for summary
        if total_energy_wh is not None:
            save_last_state(new_state, stored_power=stored_power, total_energy_wh_for_summary=total_energy_wh, notified=notified, repeat_check=False, start_time=start_time)

        # ⚡ Handle charging start
        if last_state != "charging" and new_state == "charging":
            send_notification(f"🪫 {timestamp}: charging started.")
            save_last_state("charging", stored_power=total_energy_wh, total_energy_wh_for_summary=total_energy_wh_for_summary, notified=False, start_time=current_time)

        # ⚡ Notify charging rate once per session
        if last_state == "charging" and charging_rate > 0 and not notified:
            send_notification(f"⚡ {timestamp}: charging rate {charging_rate} kW")
            save_last_state("charging", stored_power=stored_power, total_energy_wh_for_summary=total_energy_wh_for_summary, notified=True, start_time=start_time)

        # 🔋 Handle charging stop
        if last_state == "charging" and new_state == "idle":
            send_notification(f"🔋 {timestamp}: charging stopped.")
            save_last_state("idle", stored_power=stored_power, total_energy_wh_for_summary=total_energy_wh, start_time=start_time)

            if total_energy_wh is not None and start_time:
                elapsed_time = max(current_time - start_time, 60)  
                elapsed_formatted = format_duration(elapsed_time)

                previous_stored_power = stored_power or total_energy_wh or 0
                session_energy_wh = max(total_energy_wh - previous_stored_power, 0)

                debug(f".. session-summary \n-- stored_power: {stored_power} \n   total_energy_wh: {total_energy_wh} \n   previous_stored_power: {previous_stored_power} \n   session_energy_wh: {session_energy_wh} \n   start_time: {start_time} \n   current_time: {current_time} \n   elapsed_time: {elapsed_time}")

                if format_energy(session_energy_wh) == format_energy(total_energy_wh):
                    message = f"🔍 {format_energy(session_energy_wh)} in {elapsed_formatted}"
                else:
                    message = f"🔍 {format_energy(session_energy_wh)} of {format_energy(total_energy_wh)} in {elapsed_formatted}"
                send_notification(message)

        # 🔍 Log final state
        state_data = get_last_state()
        debug(f".. get_last_state() #2 \n-- state file: \n   Last State: {state_data['state']} \n   Start Time: {state_data['start_time']} \n   Stored Power: {state_data['stored_power']} \n   Total Energy for Summary: {state_data['total_energy_wh_for_summary']} \n   Notified: {state_data['notified']} \n   Repeat Check: {state_data['repeat_check']} \n-- new fetch: \n   Charging Rate: {charging_rate} \n   Total Energy: {total_energy_wh}")

    except Exception as e:
        fatal_message = (f"🚨 ALERT (main): {e}")
        logger.critical(fatal_message)
        send_notification(fatal_message)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
