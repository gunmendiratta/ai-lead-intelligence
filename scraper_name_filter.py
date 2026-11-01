import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import random
import pandas as pd

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
# Major Swiss cities to search
SWISS_CITIES = [
    "Zurich", "Geneva", "Basel", "Lausanne", "Bern",
    "Lucerne", "Lugano", "Interlaken", "Zermatt", "St. Moritz",
    "Montreux", "Locarno", "Grindelwald", "Verbier", "Davos"
]

CHECKIN = "2025-11-27"
CHECKOUT = "2025-11-29"
GROUP_ADULTS = 2
FILENAME = "swiss_apartments_filtered.csv"
MAX_TOTAL_PROPERTIES = 1000  # Total across all cities
PROPERTIES_PER_CITY = MAX_TOTAL_PROPERTIES // len(SWISS_CITIES)  # Distribute evenly

def get_search_url(city):
    return f"https://www.booking.com/searchresults.html?ss={city}&checkin={CHECKIN}&checkout={CHECKOUT}&group_adults={GROUP_ADULTS}"

# ==========================================
# 🔴 EXCLUDE KEYWORDS (Skip if name contains these)
# ==========================================
EXCLUDE_KEYWORDS = [
    # English
    "hotel", "resort", "motel", "hostel", "spa", "inn",
    "boutique", "dorm", "dormitory", "backpackers",
    "camping", "camp", "glamping", "tent", "dome",
    "mobile home", "wellness", "plaza", "palace", "regency",
    # German/Swiss
    "jugendherberge", "campingplatz"
]

# ==========================================
# 🟢 INCLUDE KEYWORDS (Keep if name contains these)
# ==========================================
INCLUDE_KEYWORDS = [
    # Apartment terms
    "apartment", "apt", "flat", "studio", "condo", "penthouse",
    "loft", "residence", "aparthotel", "serviced", "suite",
    # Home/Villa terms
    "home", "house", "villa", "chalet", "cottage", "bungalow",
    "cabin", "farmhouse", "holiday home",
    # BnB/Guesthouse terms
    "bnb", "b&b", "b & b", "bed and breakfast", "guesthouse",
    "guest house", "homestay", "pension", "gasthaus", "gasthof",
    "zimmer", "ferienwohnung", "garni"
]

# Special cases that override exclude
OVERRIDE_INCLUDE = ["aparthotel", "garni"]

# ==========================================
# 🛠️ FILTERING LOGIC
# ==========================================

def should_include_property(name):
    """
    Determine if property should be included based on name.
    Returns: (should_include: bool, reason: str, matched_keyword: str)
    """
    name_lower = name.lower()
    
    # First check for override keywords (aparthotel, garni)
    for keyword in OVERRIDE_INCLUDE:
        if keyword in name_lower:
            return (True, "override_include", keyword)
    
    # Check exclude list
    for keyword in EXCLUDE_KEYWORDS:
        if keyword in name_lower:
            return (False, "excluded", keyword)
    
    # Check include list
    for keyword in INCLUDE_KEYWORDS:
        if keyword in name_lower:
            return (True, "included", keyword)
    
    # If no keywords matched, exclude by default (likely a hotel without keyword)
    return (False, "no_match", "none")


# ==========================================
# 🔍 SCRAPING FUNCTIONS
# ==========================================

def scrape_search_results_page(driver):
    """Extract property cards from search results"""
    properties = []
    try:
        time.sleep(3)
        cards = driver.find_elements(By.CSS_SELECTOR, '[data-testid="property-card"]')
        
        for i, card in enumerate(cards):
            try:
                try:
                    name = card.find_element(By.CSS_SELECTOR, '[data-testid="title"]').text.strip()
                except:
                    name = f"Property_{i+1}"
                
                try:
                    link = card.find_element(By.CSS_SELECTOR, 'a[data-testid="title-link"]').get_attribute('href')
                    # Clean URL
                    link = link.split('?')[0] if '?' in link else link
                except:
                    continue
                
                properties.append({"name": name, "url": link})
            except:
                continue
    except Exception as e:
        print(f"  ⚠️ Error: {e}")
    
    return properties


def get_next_page_url(driver):
    """Navigate to next page"""
    try:
        next_button = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Next page"]')
        if next_button.is_enabled():
            next_button.click()
            time.sleep(2)
            return driver.current_url
    except:
        try:
            next_link = driver.find_element(By.CSS_SELECTOR, 'a[aria-label="Next page"]')
            return next_link.get_attribute('href')
        except:
            pass
    return None


# ==========================================
# 🚀 MAIN SCRAPER
# ==========================================

def main():
    print("=" * 80)
    print("🏠 NAME-BASED FILTERING SCRAPER - Switzerland Properties")
    print("=" * 80)
    
    options = uc.ChromeOptions()
    # options.add_argument('--headless')
    driver = uc.Chrome(options=options)
    
    all_properties = []  # All scanned
    filtered_properties = []  # Passed filter
    
    stats = {
        "total_scanned": 0,
        "included": 0,
        "excluded": 0,
        "override_include": 0,
        "no_match": 0
    }

    try:
        print(f"\n🌍 Searching: {DESTINATION} (No URL filters)")
        print(f"🎯 Target: Up to {MAX_PROPERTIES} properties")
        print(f"🔍 Using name-based keyword filtering\n")
        
        driver.get(BASE_URL)
        time.sleep(5)

        # Handle cookies
        try:
            driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
            time.sleep(1)
        except:
            pass

        page_num = 1
        properties_collected = 0
        
        while properties_collected < MAX_PROPERTIES:
            print(f"📄 Page {page_num} - Scanning...")
            
            page_properties = scrape_search_results_page(driver)
            
            if not page_properties:
                print("  ⚠️ No properties found. Stopping.")
                break
            
            print(f"  📦 Found {len(page_properties)} properties on page")
            
            # Filter each property by name
            for prop in page_properties:
                properties_collected += 1
                stats["total_scanned"] += 1
                
                should_include, reason, keyword = should_include_property(prop['name'])
                
                if should_include:
                    filtered_properties.append({
                        "property_name": prop['name'],
                        "booking_url": prop['url'],
                        "filter_reason": reason,
                        "matched_keyword": keyword
                    })
                    stats[reason] += 1
                    print(f"    ✅ [{properties_collected}] KEEP: {prop['name'][:60]} (matched: {keyword})")
                else:
                    stats[reason] += 1
                    print(f"    ⏭️  [{properties_collected}] SKIP: {prop['name'][:60]} (reason: {keyword})")
                
                if properties_collected >= MAX_PROPERTIES:
                    break
            
            print(f"  📊 Running total - Scanned: {stats['total_scanned']}, Kept: {stats['included'] + stats['override_include']}, Skipped: {stats['excluded'] + stats['no_match']}")
            
            if properties_collected >= MAX_PROPERTIES:
                print(f"\n🎉 Reached target of {MAX_PROPERTIES} properties!")
                break
            
            # Next page
            print("  🔄 Next page...")
            next_url = get_next_page_url(driver)
            
            if next_url:
                if next_url != driver.current_url:
                    driver.get(next_url)
                time.sleep(random.uniform(3, 5))
                page_num += 1
            else:
                print("  ℹ️ No more pages.")
                break

        # Save results
        print("\n💾 Saving filtered results...")
        df = pd.DataFrame(filtered_properties)
        df.to_csv(FILENAME, index=False, encoding='utf-8-sig')
        
        print("=" * 80)
        print(f"✅ SCRAPING COMPLETE!")
        print(f"📁 File saved: {FILENAME}")
        print("=" * 80)
        
        # Statistics
        print("\n📊 FILTERING STATISTICS:")
        print(f"  - Total scanned: {stats['total_scanned']}")
        print(f"  - ✅ Included (matched keyword): {stats['included']}")
        print(f"  - ✅ Override include (aparthotel/garni): {stats['override_include']}")
        print(f"  - ❌ Excluded (hotel/resort/etc): {stats['excluded']}")
        print(f"  - ❌ No match (default exclude): {stats['no_match']}")
        print(f"  - 📝 Total saved to CSV: {len(df)}")
        
        if len(df) > 0:
            print("\n🔑 TOP MATCHED KEYWORDS:")
            print(df['matched_keyword'].value_counts().head(10).to_string())
            
            print("\n📋 SAMPLE RESULTS (First 10):")
            print(df[['property_name', 'matched_keyword']].head(10).to_string())
            
            print("\n📋 SAMPLE RESULTS (Last 10):")
            print(df[['property_name', 'matched_keyword']].tail(10).to_string())

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n🔒 Closing browser...")
        driver.quit()
        
        # Emergency save if needed
        if filtered_properties and len(filtered_properties) > 0:
            print(f"✅ Final save confirmed: {len(filtered_properties)} properties in CSV")


if __name__ == "__main__":
    main()
