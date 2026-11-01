import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import random
import pandas as pd

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
DESTINATION = "Switzerland"
CHECKIN = "2025-11-27"
CHECKOUT = "2025-11-29"
GROUP_ADULTS = 2
MAX_PROPERTIES = 1000
SAVE_DIRECTORY = "/Users/varun/Desktop"
FILENAME = f"{SAVE_DIRECTORY}/switzerland_apartments_filtered.csv"

# URL with apartment filter (ht_id=201)
BASE_URL = f"https://www.booking.com/searchresults.html?ss={DESTINATION}&checkin={CHECKIN}&checkout={CHECKOUT}&group_adults={GROUP_ADULTS}&nflt=ht_id%3D201"

# ==========================================
# 🔴 EXCLUDE KEYWORDS (Still exclude hotels that slip through)
# ==========================================
EXCLUDE_KEYWORDS = [
    "hotel", "resort", "motel", "hostel", "spa", "inn",
    "boutique", "dorm", "dormitory", "backpackers",
    "camping", "camp", "glamping", "tent", "dome",
    "mobile home", "wellness", "plaza", "palace", "regency",
    "jugendherberge", "campingplatz"
]

OVERRIDE_INCLUDE = ["aparthotel", "garni"]

# ==========================================
# 🛠️ HELPER FUNCTIONS
# ==========================================

def should_include_property(name):
    """Include everything except hotel keywords"""
    name_lower = name.lower()
    
    # Override: aparthotel/garni are OK
    for keyword in OVERRIDE_INCLUDE:
        if keyword in name_lower:
            return (True, keyword)
    
    # Exclude hotel keywords
    for keyword in EXCLUDE_KEYWORDS:
        if keyword in name_lower:
            return (False, f"excluded:{keyword}")
    
    # Include everything else
    return (True, "included")


def load_more_results(driver):
    """Click 'Load more results' button"""
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Search all buttons for "Load more"
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for button in buttons:
            button_text = button.text.lower()
            if "load more" in button_text:
                if button.is_displayed() and button.is_enabled():
                    print(f"    🔄 Clicking 'Load more results'...")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                    time.sleep(1)
                    button.click()
                    time.sleep(4)
                    return True
    except:
        pass
    
    # Try XPath methods
    try:
        xpaths = [
            "//button[contains(text(), 'Load more')]",
            "//button[contains(text(), 'load more')]"
        ]
        for xpath in xpaths:
            try:
                load_more = driver.find_element(By.XPATH, xpath)
                if load_more.is_displayed() and load_more.is_enabled():
                    driver.execute_script("arguments[0].click();", load_more)
                    time.sleep(4)
                    return True
            except:
                continue
    except:
        pass
    
    return False


def scrape_all_properties(driver):
    """Get all currently visible properties"""
    properties = []
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        
        cards = driver.find_elements(By.CSS_SELECTOR, '[data-testid="property-card"]')
        
        for i, card in enumerate(cards):
            try:
                try:
                    name = card.find_element(By.CSS_SELECTOR, '[data-testid="title"]').text.strip()
                except:
                    name = f"Property_{i+1}"
                
                try:
                    link = card.find_element(By.CSS_SELECTOR, 'a[data-testid="title-link"]').get_attribute('href')
                    link = link.split('?')[0] if '?' in link else link
                except:
                    continue
                
                if link not in [p['url'] for p in properties]:
                    properties.append({"name": name, "url": link})
            except:
                continue
    except Exception as e:
        print(f"  ⚠️ Error: {e}")
    
    return properties


# ==========================================
# 🚀 MAIN SCRAPER
# ==========================================

def main():
    print("=" * 80)
    print("🏠 SWITZERLAND APARTMENT SCRAPER - With Load More")
    print("=" * 80)
    
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    
    filtered_properties = []
    all_scraped_urls = set()
    stats = {
        "total_scanned": 0,
        "included": 0,
        "excluded": 0
    }

    try:
        print(f"\n🌍 Searching: {DESTINATION}")
        print(f"🏢 Filter: Apartments only (URL pre-filtered)")
        print(f"🎯 Target: {MAX_PROPERTIES} properties\n")
        
        driver.get(BASE_URL)
        time.sleep(5)

        # Handle cookies
        try:
            driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
            time.sleep(1)
        except:
            pass

        load_count = 1
        no_new_count = 0
        
        while stats["total_scanned"] < MAX_PROPERTIES:
            print(f"\n📄 Load #{load_count}...")
            
            # Get all visible properties
            all_properties = scrape_all_properties(driver)
            new_properties = [p for p in all_properties if p['url'] not in all_scraped_urls]
            
            if not new_properties:
                no_new_count += 1
                print(f"  ℹ️ No new properties")
                if no_new_count >= 2:
                    print(f"  ℹ️ Stopping - no more new properties")
                    break
            else:
                no_new_count = 0
            
            print(f"  📦 Found {len(new_properties)} new properties ({len(all_properties)} total visible)")
            
            # Filter new properties
            for prop in new_properties:
                if stats["total_scanned"] >= MAX_PROPERTIES:
                    break
                
                all_scraped_urls.add(prop['url'])
                stats["total_scanned"] += 1
                
                should_include, keyword = should_include_property(prop['name'])
                
                if should_include:
                    filtered_properties.append({
                        "property_name": prop['name'],
                        "booking_url": prop['url'],
                        "matched_keyword": keyword
                    })
                    stats["included"] += 1
                    print(f"    ✅ [{stats['total_scanned']}] {prop['name'][:55]} ({keyword})")
                else:
                    stats["excluded"] += 1
                    if stats["total_scanned"] % 10 == 0:
                        print(f"    ⏭️  [{stats['total_scanned']}] {prop['name'][:55]} ({keyword})")
            
            print(f"  📊 Progress: {stats['total_scanned']} scanned, {stats['included']} kept, {stats['excluded']} excluded")
            
            # Try load more
            if stats["total_scanned"] < MAX_PROPERTIES:
                print(f"  🔍 Looking for Load More button...")
                if not load_more_results(driver):
                    print(f"  ℹ️ No Load More button found")
                    break
                load_count += 1
            else:
                print(f"\n🎉 Reached {MAX_PROPERTIES} properties!")
                break

        # Save results
        print("\n💾 Saving results...")
        df = pd.DataFrame(filtered_properties)
        df.to_csv(FILENAME, index=False, encoding='utf-8-sig')
        
        print("=" * 80)
        print(f"✅ SCRAPING COMPLETE!")
        print(f"📁 File: {FILENAME}")
        print("=" * 80)
        
        print("\n📊 STATISTICS:")
        print(f"  - Total scanned: {stats['total_scanned']}")
        print(f"  - ✅ Included: {stats['included']}")
        print(f"  - ❌ Excluded: {stats['excluded']}")
        
        if len(df) > 0:
            print(f"\n📋 SAMPLE PROPERTIES (First 10):")
            for idx, row in df.head(10).iterrows():
                print(f"  {idx+1}. {row['property_name'][:70]}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n🔒 Closing browser...")
        driver.quit()


if __name__ == "__main__":
    main()
