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
import os


output_dir = "output"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

def save_results_csv(results, owner_name):
    filename = f"{owner_name}_nikke_stats.csv" if owner_name != "N/A" else "nikke_stats.csv"
    file_path = os.path.join(output_dir, filename)  # Save to the output directory
    with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["unit_name", "overview", "skills"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for unit in results:
            overview_str = "; ".join([f"{stat['stat']}: {stat['value']}" for stat in unit.get("overview", [])])
            skills_str = "; ".join([f"{skill['skill']}: {skill['level']}" for skill in unit.get("skills", [])])
            writer.writerow({
                "unit_name": unit.get("unit_name", "N/A"),
                "overview": overview_str,
                "skills": skills_str
            })
    print(f"Progress saved to {file_path}")

def save_results_json(results, owner_name):
    filename = f"{owner_name}_nikke_stats.json" if owner_name != "N/A" else "nikke_stats.json"
    file_path = os.path.join(output_dir, filename)  # Save to the output directory
    with open(file_path, "w", encoding="utf-8") as jsonfile:
        json.dump(results, jsonfile, indent=4, ensure_ascii=False)
    print(f"Progress saved to {file_path}")

def save_summary_json(results, owner_name):
    summary = []
    for unit in results:
        summary.append({
            "unit_name": unit.get("unit_name", "N/A"),
            "overview": unit.get("overview", []),
            "skills": unit.get("skills", [])
        })
    filename = f"{owner_name}_nikke_summary.json" if owner_name != "N/A" else "nikke_summary.json"
    file_path = os.path.join(output_dir, filename)  # Save to the output directory
    with open(file_path, "w", encoding="utf-8") as jsonfile:
        json.dump(summary, jsonfile, indent=4, ensure_ascii=False)
    print(f"Summary saved to {file_path}")

# Connect to an existing Chrome session with remote debugging enabled.
chrome_options = Options()
chrome_options.debugger_address = "127.0.0.1:9222"
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)
print("Connected to existing Chrome session.")

# --- Extract Owner's Name from Homepage ---
owner_name = "N_A"
home_url = "https://www.blablalink.com/shiftyspad/home?openid=MjkwODAtNjEwODE0NzI2MzAzNDIwODQyNA=="
driver.get(home_url)
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, 'div.flex.items-center > span.font-medium'))
)
owner_name = driver.find_element(By.CSS_SELECTOR, 'div.flex.items-center > span.font-medium').text.strip()
owner_name = owner_name.replace("様", "").replace(" ", "_")
print("Owner name:", owner_name)

# --- Ask the User About Which Units to Scrape ---
user_choice = input("Scrape all units or specific units? (A/S): ").strip().lower()
scrape_specific = False
allowed_units = []
# We'll use a set to mark allowed keywords as scraped only when the base (no variation) appears.
scraped_specific = set()

if user_choice.startswith("s"):
    scrape_specific = True
    try:
        with open("units.txt", "r", encoding="utf-8") as f:
            allowed_units = [line.strip().lower() for line in f if line.strip()]
        if not allowed_units:
            print("No unit names found in units.txt. Exiting.")
            sys.exit(1)
        print("Will only scrape units matching:", allowed_units)
    except Exception as e:
        print("Error reading units.txt:", e)
        sys.exit(1)
else:
    print("Scraping all units.")

# --- Navigate to the List Page ---
list_url = "https://www.blablalink.com/shiftyspad/nikke-list?openid=MjkwODAtNjEwODE0NzI2MzAzNDIwODQyNA=="
driver.get(list_url)
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-cname="player-item"]')))
time.sleep(0.5)  # Short delay for speed

cards = driver.find_elements(By.CSS_SELECTOR, '[data-cname="player-item"]')
print(f"Found {len(cards)} unit cards.")

results = []
num_cards = len(cards)

try:
    for i in range(num_cards):
        # If scraping specific units and all base units have been scraped, break early.
        if scrape_specific and len(scraped_specific) == len(allowed_units):
            print("All specified base units scraped. Exiting loop early.")
            break

        # Refresh the list of cards to avoid stale element issues.
        cards = driver.find_elements(By.CSS_SELECTOR, '[data-cname="player-item"]')
        if i >= len(cards):
            break

        card = cards[i]
        unit_name = "N/A"
        try:
            unit_name = card.find_element(By.CSS_SELECTOR, ".name").text.strip()
        except Exception:
            pass

        # --- Filtering based on allowed units (if applicable) ---
        if scrape_specific:
            unit_name_lower = unit_name.lower()
            if not any(allowed in unit_name_lower for allowed in allowed_units):
                print(f"Skipping unit: {unit_name}")
                continue
            else:
                # Mark as scraped only if this is the base unit (no colon)
                for allowed in allowed_units:
                    if allowed in unit_name_lower and ":" not in unit_name:
                        scraped_specific.add(allowed)

        driver.execute_script("arguments[0].scrollIntoView(true);", card)
        time.sleep(0.3)

        try:
            card.click()
        except Exception as e:
            print(f"Error clicking card {i}: {e}")
            continue

        # Wait for navigation by waiting for URL change or unique element on detail page.
        WebDriverWait(driver, 10).until(EC.url_changes(list_url))
        time.sleep(0.5)

        unit_url = driver.current_url
        print(f"Processing unit {i+1}/{num_cards} - {unit_name} at {unit_url}")

        unit_html = driver.page_source
        unit_soup = BeautifulSoup(unit_html, "html.parser")
        
        # --- Extract Overview Stats ---
        overview_stats = []
        overview_container = unit_soup.find("div", class_="nikkes-detail-box")
        if overview_container:
            overview_stats_elements = overview_container.find_all(attrs={"data-cname": "equip-effect"})
            for elem in overview_stats_elements:
                span_elems = elem.find_all('span')
                stat_name = span_elems[0].get_text(strip=True) if len(span_elems) > 0 else "N/A"
                stat_value = span_elems[1].get_text(strip=True) if len(span_elems) > 1 else "N/A"
                overview_stats.append({"stat": stat_name, "value": stat_value})
        
        # --- Extract Substats (if needed) ---
        all_stats_elements = unit_soup.find_all(attrs={"data-cname": "equip-effect"})
        substats_elements = []
        if overview_container:
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
        
        # --- Extract Skills ---
        try:
            # Attempt to click the Skill tab if it exists.
            skill_tab = driver.find_element(By.XPATH, '//div[@data-cname="NavTab"]//div[text()="Skill"]')
            skill_tab.click()
            print("Clicked on the Skill tab.")
        except Exception as e:
            print("Error clicking on the Skill tab:", e)
        
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-cname="WeaponSkill"]')))
        time.sleep(0.5)
        
        skill_html = driver.page_source
        skill_soup = BeautifulSoup(skill_html, "html.parser")
        skill_elements = skill_soup.find_all("div", {"data-cname": "WeaponSkill"})
        
        skills = []
        for elem in skill_elements:
            skill_name_elem = elem.find("p", class_="text-ink")
            skill_name = skill_name_elem.get_text(strip=True) if skill_name_elem else "N/A"
            level_span = elem.find("span", class_="text-20 text-white ff-num text-highlight-blue")
            skill_level = level_span.get_text(strip=True) if level_span else "N/A"
            skills.append({"skill": skill_name, "level": skill_level})
        
        print(f"Extracted skills: {skills}")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        results.append({
            "unit_url": unit_url,
            "unit_name": unit_name,
            "overview": overview_stats,
            "substats": substats,
            "skills": skills,
            "timestamp": timestamp
        })
        
        print(f"Extracted {len(overview_stats)} overview stats, {len(substats)} substats, and {len(skills)} skills from {unit_name}.")
        
        driver.back()
        WebDriverWait(driver, 10).until(EC.url_to_be(list_url))
        time.sleep(0.5)

except KeyboardInterrupt:
    print("Scraping interrupted by user!")
    save_results_csv(results, owner_name)
    save_results_json(results, owner_name)
    save_summary_json(results, owner_name)
    sys.exit(0)

driver.quit()
save_results_csv(results, owner_name)
save_results_json(results, owner_name)
save_summary_json(results, owner_name)
print(f"Scraping complete. Data saved as {owner_name}_nikke_stats.csv, {owner_name}_nikke_stats.json, and {owner_name}_nikke_summary.json")
