import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import random
import pandas as pd

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
# Set to "ALL" to scrape all cities, or pick one: "Zurich", "Geneva", etc.
CITY_TO_SCRAPE = "ALL"  # Changed to ALL

# Available Swiss cities
SWISS_CITIES = [
    "Zurich", "Geneva", "Basel", "Lausanne", "Bern",
    "Lucerne", "Lugano", "Interlaken", "Zermatt", "St. Moritz",
    "Montreux", "Locarno", "Grindelwald", "Verbier", "Davos"
]

CHECKIN = "2025-11-27"
CHECKOUT = "2025-11-29"
GROUP_ADULTS = 2
MAX_PER_CITY = 1000  # Max 1000 properties per city

# Save all files in Desktop directory
SAVE_DIRECTORY = "/Users/varun/Desktop"

def get_filename(city):
    return f"{SAVE_DIRECTORY}/{city.lower().replace(' ', '_')}_apartments.csv"

def get_search_url(city):
    return f"https://www.booking.com/searchresults.html?ss={city},Switzerland&checkin={CHECKIN}&checkout={CHECKOUT}&group_adults={GROUP_ADULTS}"

# ==========================================
# 🔴 EXCLUDE KEYWORDS ONLY (Skip if name contains these)
# ==========================================
EXCLUDE_KEYWORDS = [
    # English - Hotels/Resorts only
    "hotel", "resort", "motel", "hostel", "spa", "inn",
    "boutique", "dorm", "dormitory", "backpackers",
    "camping", "camp", "glamping", "tent", "dome",
    "mobile home", "wellness", "plaza", "palace", "regency",
    # German/Swiss
    "jugendherberge", "campingplatz"
]

# Special cases that should NOT be excluded even if they contain "hotel"
OVERRIDE_INCLUDE = ["aparthotel", "garni"]

# ==========================================
# 🛠️ FILTERING LOGIC
# ==========================================

def should_include_property(name):
    """
    Determine if property should be included based on name.
    INCLUDE everything EXCEPT the exclude keywords.
    """
    name_lower = name.lower()
    
    # Check override keywords first (aparthotel, garni) - always include these
    for keyword in OVERRIDE_INCLUDE:
        if keyword in name_lower:
            return (True, keyword)
    
    # Check exclude list - skip these
    for keyword in EXCLUDE_KEYWORDS:
        if keyword in name_lower:
            return (False, f"excluded:{keyword}")
    
    # Default: INCLUDE everything else
    return (True, "included")


# ==========================================
# 🔍 SCRAPING FUNCTIONS
# ==========================================

def scrape_search_results_page(driver):
    """Extract property cards from search results (including dynamically loaded)"""
    properties = []
    try:
        # Scroll to bottom to trigger any lazy loading
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Scroll back up
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
                
                # Avoid duplicates
                if link not in [p['url'] for p in properties]:
                    properties.append({"name": name, "url": link})
            except:
                continue
    except Exception as e:
        print(f"  ⚠️ Error: {e}")
    
    return properties


def load_more_results(driver):
    """Click 'Load more results' button if available"""
    try:
        # Scroll down to load lazy content and find button
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Method 1: Text-based search (most reliable)
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for button in buttons:
            button_text = button.text.lower()
            if "load more" in button_text:
                if button.is_displayed() and button.is_enabled():
                    print(f"    🔄 Clicking 'Load more results' button...")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                    time.sleep(1)
                    button.click()
                    time.sleep(4)  # Wait for new results to load
                    return True
    except Exception as e:
        print(f"    ⚠️ Load more button error: {e}")
    
    try:
        # Method 2: Common Booking.com selectors
        selectors = [
            'button[data-testid="pagination-load-more"]',
            'button.fc63351294',  # Booking.com class
            'div[data-testid="property-list"] + button',
            'button:has-text("Load more")'
        ]
        
        for selector in selectors:
            try:
                load_more = driver.find_element(By.CSS_SELECTOR, selector)
                if load_more.is_displayed() and load_more.is_enabled():
                    print(f"    🔄 Found load button with selector: {selector}")
                    driver.execute_script("arguments[0].click();", load_more)
                    time.sleep(4)
                    return True
            except:
                continue
    except:
        pass
    
    # Method 3: XPath search
    try:
        xpaths = [
            "//button[contains(text(), 'Load more')]",
            "//button[contains(text(), 'load more')]",
            "//button[contains(@class, 'load') and contains(@class, 'more')]"
        ]
        
        for xpath in xpaths:
            try:
                load_more = driver.find_element(By.XPATH, xpath)
                if load_more.is_displayed() and load_more.is_enabled():
                    print(f"    🔄 Found via XPath")
                    driver.execute_script("arguments[0].click();", load_more)
                    time.sleep(4)
                    return True
            except:
                continue
    except:
        pass
    
    return False


def get_next_page_url(driver):
    """Try to navigate to next page or load more results"""
    # First try "Load more" button
    if load_more_results(driver):
        return driver.current_url
    
    # Fallback: Try traditional next page button
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
# 🚀 SCRAPE ONE CITY
# ==========================================

def scrape_city(driver, city):
    """Scrape one city, max 1000 properties"""
    print(f"\n{'='*80}")
    print(f"🏙️  SCRAPING: {city}, Switzerland")
    print(f"{'='*80}")
    
    filtered_properties = []
    all_scraped_urls = set()  # Track URLs to avoid duplicates
    stats = {
        "total_scanned": 0,
        "included": 0,
        "excluded": 0
    }
    
    try:
        driver.get(get_search_url(city))
        time.sleep(5)
        
        load_count = 1
        no_new_properties_count = 0
        
        while stats["total_scanned"] < MAX_PER_CITY:
            print(f"\n📄 Load #{load_count}...")
            
            # Get all currently visible properties
            page_properties = scrape_search_results_page(driver)
            
            # Filter for new properties only
            new_properties = [p for p in page_properties if p['url'] not in all_scraped_urls]
            
            if not new_properties:
                no_new_properties_count += 1
                print(f"  ℹ️ No new properties found")
                if no_new_properties_count >= 2:
                    print(f"  ℹ️ No more new properties available")
                    break
            else:
                no_new_properties_count = 0
            
            print(f"  📦 Found {len(new_properties)} new properties ({len(page_properties)} total visible)")
            
            # Filter each NEW property
            for prop in new_properties:
                if stats["total_scanned"] >= MAX_PER_CITY:
                    break
                
                all_scraped_urls.add(prop['url'])
                stats["total_scanned"] += 1
                
                should_include, keyword = should_include_property(prop['name'])
                
                if should_include:
                    filtered_properties.append({
                        "city": city,
                        "property_name": prop['name'],
                        "booking_url": prop['url'],
                        "matched_keyword": keyword
                    })
                    stats["included"] += 1
                    print(f"    ✅ [{stats['total_scanned']}] {prop['name'][:55]} ({keyword})")
                else:
                    stats["excluded"] += 1
                    # Show every 10th skip to reduce noise
                    if stats["total_scanned"] % 10 == 0:
                        print(f"    ⏭️  [{stats['total_scanned']}] {prop['name'][:55]} ({keyword})")
            
            print(f"  📊 Progress: {stats['total_scanned']} scanned, {stats['included']} kept, {stats['excluded']} excluded")
            
            # Try to load more
            if stats["total_scanned"] < MAX_PER_CITY:
                print(f"  🔍 Attempting to load more results...")
                
                # Debug: Check what buttons exist on page
                try:
                    all_buttons = driver.find_elements(By.TAG_NAME, "button")
                    button_texts = [btn.text[:50] for btn in all_buttons if btn.text.strip()]
                    print(f"  📝 Buttons found on page: {button_texts[:10]}")  # Show first 10
                except:
                    pass
                
                if not get_next_page_url(driver):
                    print(f"  ℹ️ No more pages/load button available")
                    break
                load_count += 1
            else:
                print(f"\n🎉 Reached max {MAX_PER_CITY} for {city}!")
                break
        
        # Save results for this city
        filename = get_filename(city)
        df = pd.DataFrame(filtered_properties)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        
        print(f"\n✅ {city} COMPLETE!")
        print(f"  - Scanned: {stats['total_scanned']}")
        print(f"  - Kept: {stats['included']}")
        print(f"  - Excluded: {stats['excluded']}")
        print(f"  - File: {filename}")
        
        if len(df) > 0:
            print(f"\n� Sample properties saved:")
            for idx, row in df.head(5).iterrows():
                print(f"    - {row['property_name'][:60]}")
        
        return filtered_properties
        
    except Exception as e:
        print(f"❌ Error scraping {city}: {e}")
        import traceback
        traceback.print_exc()
        return filtered_properties


# ==========================================
# 🚀 MAIN
# ==========================================

def main():
    print("=" * 80)
    print("🏠 SWISS PROPERTY SCRAPER - Name-Based Filtering")
    print("=" * 80)
    
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    
    try:
        # Handle cookies once
        driver.get(get_search_url("Zurich"))
        time.sleep(5)
        try:
            driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
            time.sleep(1)
        except:
            pass
        
        # Decide which cities to scrape
        if CITY_TO_SCRAPE == "ALL":
            print(f"\n🌍 Scraping ALL {len(SWISS_CITIES)} cities")
            print(f"📊 Max {MAX_PER_CITY} properties per city\n")
            
            all_results = []
            for idx, city in enumerate(SWISS_CITIES, 1):
                print(f"\n[City {idx}/{len(SWISS_CITIES)}]")
                results = scrape_city(driver, city)
                all_results.extend(results)
                time.sleep(3)  # Pause between cities
            
            # Save combined file
            if all_results:
                combined_df = pd.DataFrame(all_results)
                combined_file = f"{SAVE_DIRECTORY}/all_swiss_cities_apartments.csv"
                combined_df.to_csv(combined_file, index=False, encoding='utf-8-sig')
                print(f"\n✅ Combined file saved: {combined_file} ({len(combined_df)} properties)")
                
                # Summary by city
                print(f"\n📊 PROPERTIES BY CITY:")
                city_counts = {}
                for result in all_results:
                    city_counts[result.get('city', 'Unknown')] = city_counts.get(result.get('city', 'Unknown'), 0) + 1
                for city, count in sorted(city_counts.items()):
                    print(f"  - {city}: {count} properties")
        
        else:
            # Single city
            if CITY_TO_SCRAPE in SWISS_CITIES:
                print(f"\n🏙️  Target: {CITY_TO_SCRAPE}")
                print(f"📊 Max: {MAX_PER_CITY} properties\n")
                scrape_city(driver, CITY_TO_SCRAPE)
            else:
                print(f"❌ Error: '{CITY_TO_SCRAPE}' not in available cities")
                print(f"Available: {', '.join(SWISS_CITIES)}")
    
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n🔒 Closing browser...")
        driver.quit()


if __name__ == "__main__":
    main()
