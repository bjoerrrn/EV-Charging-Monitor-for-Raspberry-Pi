#!/usr/bin/env python3

import time
import logging
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

LOG_FILE = "/home/pi/test_consumed.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

WALLBOX_URL = "http://192.168.178.51:12800/user/user.html"

def get_browser():
    """Starts a headless browser session using Chromium."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service("/usr/lib/chromium-browser/chromedriver")
    return webdriver.Chrome(service=service, options=options)

def test_consumed_value(driver):
    """Continuously checks for the 'consumed' field until it appears or timeout."""
    driver.get(WALLBOX_URL)
    found = False

    for attempt in range(20):  # Check every 3 seconds, max 60 sec
        try:
            consumed_element = driver.find_element(By.ID, "consumed")
            consumed_text = consumed_element.get_attribute("value")

            match = re.search(r"([\d.]+)\s*(wh|kWh)", consumed_text)
            if match:
                value = float(match.group(1))
                if "kWh" in consumed_text:
                    value *= 1000  # Convert to Wh
                print(f"✅ Found consumed energy: {value} Wh")
                logging.info(f"✅ Found consumed energy: {value} Wh")
                found = True
                break
        except Exception:
            print(f"⏳ Attempt {attempt + 1}: 'consumed' not found yet.")
            logging.info(f"⏳ Attempt {attempt + 1}: 'consumed' not found yet.")

        time.sleep(3)

    if not found:
        print("❌ Failed to detect 'consumed' within 60 seconds.")
        logging.error("❌ Failed to detect 'consumed' within 60 seconds.")

if __name__ == "__main__":
    driver = get_browser()
    try:
        test_consumed_value(driver)
    finally:
        driver.quit()
