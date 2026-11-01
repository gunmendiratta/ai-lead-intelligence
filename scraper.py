import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import time
import random
import re
import pandas as pd

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
DESTINATION = "Switzerland"
CHECKIN = "2025-11-27"
CHECKOUT = "2025-11-29"
GROUP_ADULTS = 2
FILENAME = "swiss_apartments.csv"
MAX_STAGE1_SCAN = 6000
MAX_STAGE2_PROCESS = 1000

# Filters: Apartments (201), B&Bs (220), Guesthouses (216)
BASE_URL = f"https://www.booking.com/searchresults.html?ss={DESTINATION}&checkin={CHECKIN}&checkout={CHECKOUT}&group_adults={GROUP_ADULTS}&nflt=ht_id%3D201;ht_id%3D220;ht_id%3D216"

ALLOWED_PROPERTY_TYPES = [
    "apartment", "aparthotel", "serviced apartment",
    "bed and breakfast", "b&b", "bnb", "b & b",
    "guesthouse", "guest house", "inn", "hostel"
]

PHONE_REGEX = r'(?:\+41|0041|0)\s?[1-9]\d{1,2}\s?\d{3}\s?\d{2}\s?\d{2}'

# ==========================================
# 🛠️ HELPER FUNCTIONS
# ==========================================

def is_allowed_property_type(property_type_text):
    if not property_type_text: return False
    return any(t in property_type_text.lower() for t in ALLOWED_PROPERTY_TYPES)

def get_property_type_quick(driver, url):
    """Quick check to get property type without full scrape"""
    original_window = driver.current_window_handle
    property_type = "Apartment" # Default
    
    try:
        driver.switch_to.new_window('tab')
        driver.get(url)
        time.sleep(2) # Short wait
        
        # Method 1: Header
        try:
            heading = driver.find_element(By.TAG_NAME, 'h1').text.lower()
            heading += " " + driver.find_element(By.CSS_SELECTOR, 'div[data-capla-component-boundary*="PropertyHeaderName"]').text.lower()
            for allowed in ALLOWED_PROPERTY_TYPES:
                if allowed in heading:
                    property_type = allowed.title()
                    break
        except:
            pass

    except Exception:
        pass
    finally:
        driver.close()
        driver.switch_to.window(original_window)
    
    return property_type

def scrape_comprehensive_details(driver, url, property_name):
    """Deep scrape: Extract all details"""
    data = {
        "property_name": property_name,
        "booking_url": url,
        "accurate_address": "N/A",
        "city": "N/A",
        "postal_code": "N/A",
        "managed_by_company": "No",
        "company_name": "N/A",
        "latitude": None,
        "longitude": None,
        "phone": "N/A",
        "description": "",
        "amenities": "",
        "property_type": "Apartment"
    }
    
    original_window = driver.current_window_handle
    try:
        driver.switch_to.new_window('tab')
        driver.get(url)
        time.sleep(random.uniform(2, 4))
        
        # 1. Address
        try:
            address_elem = driver.find_element(By.CSS_SELECTOR, '[data-testid="address"]')
            data["accurate_address"] = address_elem.text.strip()
            parts = data["accurate_address"].split(',')
            data["city"] = parts[-1].strip() if parts else "N/A"
        except: pass

        # 2. Managed by Company
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            if "managed by" in body_text or "property management" in body_text:
                data["managed_by_company"] = "Yes"
                try:
                    host = driver.find_element(By.CSS_SELECTOR, '[data-testid="property-owner-block"]')
                    data["company_name"] = host.text.split('\n')[0]
                except: pass
        except: pass
        
        # 3. Coordinates
        try:
            map_link = driver.find_element(By.CSS_SELECTOR, "#hotel_header_map_link")
            coords = map_link.get_attribute("data-atlas-latlng")
            if coords:
                lat, lng = coords.split(",")
                data["latitude"], data["longitude"] = float(lat), float(lng)
        except: pass

        # 4. Phone (Regex scan)
        try:
            matches = re.findall(PHONE_REGEX, driver.page_source)
            if matches: data["phone"] = matches[0]
        except: pass

    except Exception as e:
        print(f"  ⚠️ Details Error: {e}")
    finally:
        driver.close()
        driver.switch_to.window(original_window)
    
    return data

def scrape_visible_cards(driver, seen_urls):
    """Scrapes currently visible cards, ignoring ones we've already seen"""
    new_properties = []
    try:
        cards = driver.find_elements(By.CSS_SELECTOR, '[data-testid="property-card"]')
        
        for card in cards:
            try:
                link_el = card.find_element(By.CSS_SELECTOR, 'a[data-testid="title-link"]')
                raw_url = link_el.get_attribute('href')
                clean_url = raw_url.split('?')[0]
                
                if clean_url in seen_urls:
                    continue
                
                try:
                    name = card.find_element(By.CSS_SELECTOR, '[data-testid="title"]').text.strip()
                except:
                    name = "Unknown Property"

                seen_urls.add(clean_url)
                new_properties.append({"name": name, "url": clean_url})
            except:
                continue
    except Exception as e:
        print(f"  ⚠️ Error reading cards: {e}")
        
    return new_properties

def handle_pagination(driver):
    """
    Tries to click 'Load more results' (AJAX). 
    If not found, tries standard 'Next page' (URL change).
    Returns: True if content loaded/navigated, False if end reached.
    """
    # STRATEGY 1: Look for "Load more results" button (AJAX append)
    try:
        # Use XPath to find button by text, handles different languages if needed adjust text
        load_more_btn = driver.find_element(By.XPATH, "//button[contains(., 'Load more results') or contains(., 'Show more results')]")
        
        if load_more_btn.is_displayed():
            print("  🖱️  Clicking 'Load more results'...")
            # Scroll to it
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_btn)
            time.sleep(1)
            # Click via JS to avoid footer obstruction
            driver.execute_script("arguments[0].click();", load_more_btn)
            time.sleep(4) # Wait for AJAX load
            return True
    except NoSuchElementException:
        pass
    except Exception as e:
        print(f"  ⚠️ Error clicking Load More: {e}")

    # STRATEGY 2: Standard Pagination (Page 1, 2, 3...)
    try:
        next_btn = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Next page"]')
        if next_btn.is_enabled():
            print("  ➡️  Clicking Standard 'Next Page'...")
            next_btn.click()
            time.sleep(4)
            return True
    except:
        pass
        
    return False

# ==========================================
# 🚀 MAIN SCRAPER
# ==========================================

def main():
    print("=" * 70)
    print("🚀 BOOKING.COM APARTMENT SCRAPER (FIXED)")
    print("=" * 70)
    
    options = uc.ChromeOptions()
    # options.add_argument('--headless') # Keep off for debugging
    driver = uc.Chrome(options=options)
    
    all_basic_data = []
    all_comprehensive_data = []
    seen_urls = set()

    try:
        # ========================================
        # STAGE 1: Collect URLs (Infinite Scroll/Pagination)
        # ========================================
        print(f"\n📋 STAGE 1: Searching {DESTINATION}...")
        driver.get(BASE_URL)
        time.sleep(5)

        # Cookie Banner
        try:
            driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
        except: pass

        while len(all_basic_data) < MAX_STAGE1_SCAN:
            # 1. Scrape what is currently visible
            new_props = scrape_visible_cards(driver, seen_urls)
            if new_props:
                all_basic_data.extend(new_props)
                print(f"  ✅ Collected {len(new_props)} new (Total: {len(all_basic_data)})")
            
            if len(all_basic_data) >= MAX_STAGE1_SCAN:
                break

            # 2. Try to load more content
            has_more = handle_pagination(driver)
            if not has_more:
                print("  🛑 No more pages or 'Load More' buttons found.")
                break
        
        print(f"\n✅ STAGE 1 DONE. Total Properties: {len(all_basic_data)}")
        
        # ========================================
        # STAGE 2: Deep Scrape
        # ========================================
        print(f"\n📊 STAGE 2: Processing first {MAX_STAGE2_PROCESS} properties...")
        
        for idx, prop in enumerate(all_basic_data[:MAX_STAGE2_PROCESS], 1):
            print(f"[{idx}] {prop['name'][:40]}...", end=" ")
            
            # Filter Logic
            p_type = get_property_type_quick(driver, prop['url'])
            if not is_allowed_property_type(p_type):
                print(f"❌ Skipped ({p_type})")
                continue
            
            print(f"✅ Deep Scraping...")
            details = scrape_comprehensive_details(driver, prop['url'], prop['name'])
            details['property_type'] = p_type
            all_comprehensive_data.append(details)
            
            if len(all_comprehensive_data) % 10 == 0:
                pd.DataFrame(all_comprehensive_data).to_csv(f"checkpoint_{FILENAME}", index=False)

        # Save Final
        pd.DataFrame(all_comprehensive_data).to_csv(FILENAME, index=False)
        print(f"\n🎉 Finished! Saved {len(all_comprehensive_data)} rows to {FILENAME}")

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()