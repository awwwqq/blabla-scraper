import time
import json
import sys
import csv
from datetime import datetime 
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

def save_results_csv(results):
    with open("nikke_stats.csv", "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["unit_name", "overview"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for unit in results:
            overview_str = "; ".join([f"{stat['stat']}: {stat['value']}" for stat in unit["overview"]])
            writer.writerow({
                "unit_name": unit["unit_name"],
                "overview": overview_str
            })
    print("Progress saved to nikke_stats.csv")


def save_results_json(results):
    with open("nikke_stats.json", "w", encoding="utf-8") as jsonfile:
        json.dump(results, jsonfile, indent=4, ensure_ascii=False)
    print("Progress saved to nikke_stats.json")

chrome_options = Options()
chrome_options.debugger_address = "127.0.0.1:9222"

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)
print("Connected to existing Chrome session.")

# Navigate to the list page
list_url = "https://www.blablalink.com/shiftyspad/nikke-list?openid=MjkwODAtNjEwODE0NzI2MzAzNDIwODQyNA=="
driver.get(list_url)
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-cname="player-item"]')))
time.sleep(3)  # Adjust this sleep if needed

cards = driver.find_elements(By.CSS_SELECTOR, '[data-cname="player-item"]')
print(f"Found {len(cards)} unit cards.")

results = []
num_cards = len(cards)

try:
    for i in range(num_cards):
        # Re-find cards after each navigation
        cards = driver.find_elements(By.CSS_SELECTOR, '[data-cname="player-item"]')
        if i >= len(cards):
            break

        card = cards[i]
        unit_name = "N/A"
        try:
            unit_name = card.find_element(By.CSS_SELECTOR, ".name").text.strip()
        except Exception:
            pass

        driver.execute_script("arguments[0].scrollIntoView(true);", card)
        time.sleep(1)  # Delay before clicking

        try:
            card.click()
        except Exception as e:
            print(f"Error clicking card {i}: {e}")
            continue

        WebDriverWait(driver, 10).until(EC.url_changes(list_url))
        time.sleep(3)  # Allow the unit page to load

        unit_url = driver.current_url
        print(f"Processing unit {i+1}/{num_cards} - {unit_name} at {unit_url}")

        unit_html = driver.page_source
        unit_soup = BeautifulSoup(unit_html, "html.parser")
        
        # Extract overview stats from the designated container
        overview_stats = []
        overview_container = unit_soup.find("div", class_="nikkes-detail-box")
        if overview_container:
            overview_stats_elements = overview_container.find_all(attrs={"data-cname": "equip-effect"})
            for elem in overview_stats_elements:
                span_elems = elem.find_all('span')
                stat_name = span_elems[0].get_text(strip=True) if len(span_elems) > 0 else "N/A"
                stat_value = span_elems[1].get_text(strip=True) if len(span_elems) > 1 else "N/A"
                overview_stats.append({"stat": stat_name, "value": stat_value})
        
        # Extract all stats (this may include the overview ones)
        all_stats_elements = unit_soup.find_all(attrs={"data-cname": "equip-effect"})
        substats_elements = []
        if overview_container:
            # Filter out those that are part of the overview container
            overview_set = set(overview_container.find_all(attrs={"data-cname": "equip-effect"}))
            substats_elements = [elem for elem in all_stats_elements if elem not in overview_set]
        else:
            substats_elements = all_stats_elements
        
        substats = []
        for elem in substats_elements:
            span_elems = elem.find_all('span')
            stat_name = span_elems[0].get_text(strip=True) if len(span_elems) > 0 else "N/A"
            stat_value = span_elems[1].get_text(strip=True) if len(span_elems) > 1 else "N/A"
            substats.append({"stat": stat_name, "value": stat_value})
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        results.append({
            "unit_url": unit_url,
            "unit_name": unit_name,
            "overview": overview_stats,
            "substats": substats,
            "timestamp": timestamp
        })
        
        print(f"Extracted {len(overview_stats)} overview stats and {len(substats)} substats from {unit_name}.")
        
        driver.back()
        WebDriverWait(driver, 10).until(EC.url_to_be(list_url))
        time.sleep(3)  # Adjust this delay if needed

except KeyboardInterrupt:
    print("Scraping interrupted by user!")
    save_results_csv(results)
    save_results_json(results)
    sys.exit(0)

driver.quit()
save_results_csv(results)
save_results_json(results)
print("Scraping complete. Data saved to nikke_stats.csv and nikke_stats.json")
