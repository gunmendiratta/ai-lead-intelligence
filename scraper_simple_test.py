import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import random
import pandas as pd

# ==========================================
# ⚙️ CONFIGURATION (TEST VERSION)
# ==========================================
DESTINATION = "Switzerland"
CHECKIN = "2025-11-27"
CHECKOUT = "2025-11-29"
GROUP_ADULTS = 2
FILENAME = "swiss_properties_test.csv"
TEST_LIMIT = 25  # Test on first 25 properties only

# No filters - just raw Switzerland search
BASE_URL = f"https://www.booking.com/searchresults.html?ss={DESTINATION}&checkin={CHECKIN}&checkout={CHECKOUT}&group_adults={GROUP_ADULTS}"

# Property types we're looking for
TARGET_TYPES = ["apartment", "aparthotel", "b&b", "bnb", "bed and breakfast", "guesthouse", "guest house", "inn"]

# ==========================================
# 🛠️ HELPER FUNCTIONS
# ==========================================

def get_property_type_from_page(driver, url, property_name):
    """
    Open property page and try multiple methods to extract property type.
    Returns: dict with property_type and detection_method
    """
    result = {
        "property_type": "Unknown",
        "detection_method": "Failed",
        "raw_text_sample": ""
    }
    
    original_window = None
    
    try:
        original_window = driver.current_window_handle
        driver.execute_script(f"window.open('{url}');")
        time.sleep(2)
        
        new_windows = [w for w in driver.window_handles if w != original_window]
        if new_windows:
            driver.switch_to.window(new_windows[0])
            time.sleep(4)  # Give page time to fully load
            
            # METHOD 1: Look for data-testid="property-type"
            try:
                prop_elem = driver.find_element(By.CSS_SELECTOR, '[data-testid="property-type"]')
                if prop_elem:
                    result["property_type"] = prop_elem.text.strip()
                    result["detection_method"] = "data-testid"
                    return result
            except:
                pass
            
            # METHOD 2: Check page title
            try:
                page_title = driver.title
                result["raw_text_sample"] = page_title[:100]
                # Hotels usually have "Hotel" in title, apartments have "Apartment"
                title_lower = page_title.lower()
                if "hotel" in title_lower and "apart" not in title_lower:
                    result["property_type"] = "Hotel"
                    result["detection_method"] = "page_title"
                    return result
                for target in TARGET_TYPES:
                    if target in title_lower:
                        result["property_type"] = target.title()
                        result["detection_method"] = "page_title"
                        return result
            except:
                pass
            
            # METHOD 3: Look in breadcrumb navigation
            try:
                breadcrumbs = driver.find_elements(By.CSS_SELECTOR, 'nav[aria-label="Breadcrumb"] li')
                for bc in breadcrumbs:
                    text = bc.text.lower()
                    if "hotel" in text and "apart" not in text:
                        result["property_type"] = "Hotel"
                        result["detection_method"] = "breadcrumb"
                        return result
                    for target in TARGET_TYPES:
                        if target in text:
                            result["property_type"] = target.title()
                            result["detection_method"] = "breadcrumb"
                            return result
            except:
                pass
            
            # METHOD 4: Scan first 1500 chars of page text
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text
                text_sample = body_text[:1500].lower()
                result["raw_text_sample"] = text_sample[:200]
                
                # Count occurrences
                hotel_count = text_sample.count("hotel")
                apartment_count = text_sample.count("apartment")
                
                # If "hotel" appears significantly more than "apartment", likely a hotel
                if hotel_count >= 3 and hotel_count > apartment_count * 2:
                    result["property_type"] = "Hotel"
                    result["detection_method"] = "text_frequency"
                    return result
                
                # Check for our target types
                for target in TARGET_TYPES:
                    if target in text_sample:
                        result["property_type"] = target.title()
                        result["detection_method"] = "body_text_scan"
                        return result
            except:
                pass
            
            # METHOD 5: Check meta tags
            try:
                meta_desc = driver.find_element(By.CSS_SELECTOR, 'meta[name="description"]')
                if meta_desc:
                    content = meta_desc.get_attribute("content").lower()
                    if "hotel" in content and "apart" not in content:
                        result["property_type"] = "Hotel"
                        result["detection_method"] = "meta_description"
                        return result
                    for target in TARGET_TYPES:
                        if target in content:
                            result["property_type"] = target.title()
                            result["detection_method"] = "meta_description"
                            return result
            except:
                pass
    
    except Exception as e:
        result["detection_method"] = f"Error: {str(e)[:50]}"
    
    finally:
        try:
            for handle in driver.window_handles:
                if handle != original_window:
                    driver.switch_to.window(handle)
                    driver.close()
            if original_window and original_window in driver.window_handles:
                driver.switch_to.window(original_window)
        except:
            pass
    
    return result


def scrape_search_results_page(driver):
    """Extract property cards from search results"""
    properties = []
    try:
        time.sleep(3)
        cards = driver.find_elements(By.CSS_SELECTOR, '[data-testid="property-card"]')
        print(f"  📦 Found {len(cards)} properties on this page")
        
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
                
                properties.append({"name": name, "url": link})
            except:
                continue
    except Exception as e:
        print(f"  ⚠️ Error: {e}")
    
    return properties


# ==========================================
# 🚀 MAIN TEST SCRAPER
# ==========================================

def main():
    print("=" * 70)
    print("🧪 PROPERTY TYPE DETECTION TEST - First 25 Properties")
    print("=" * 70)
    
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    
    all_data = []

    try:
        print(f"\n🌍 Searching: {DESTINATION} (No filters)")
        print(f"🎯 Testing on first {TEST_LIMIT} properties\n")
        
        driver.get(BASE_URL)
        time.sleep(5)

        # Handle cookies
        try:
            driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
            time.sleep(1)
        except:
            pass

        # Get first page properties
        print("📄 Scraping page 1...")
        properties = scrape_search_results_page(driver)
        properties = properties[:TEST_LIMIT]  # Limit to test amount
        
        print(f"\n🔍 Testing property type detection on {len(properties)} properties...\n")
        
        for idx, prop in enumerate(properties, 1):
            try:
                print(f"[{idx}/{len(properties)}] {prop['name'][:60]}...")
                
                # Check property type
                type_info = get_property_type_from_page(driver, prop['url'], prop['name'])
                
                print(f"  ✓ Type: {type_info['property_type']} (via {type_info['detection_method']})")
                
                all_data.append({
                    "property_name": prop['name'],
                    "booking_url": prop['url'],
                    "property_type": type_info['property_type'],
                    "detection_method": type_info['detection_method'],
                    "text_sample": type_info['raw_text_sample'][:100]
                })
                
                time.sleep(random.uniform(2, 3))
                
            except Exception as e:
                print(f"  ⚠️ Error: {e}")
                all_data.append({
                    "property_name": prop['name'],
                    "booking_url": prop['url'],
                    "property_type": "Error",
                    "detection_method": str(e)[:50],
                    "text_sample": ""
                })

        # Save results
        print("\n💾 Saving test results...")
        df = pd.DataFrame(all_data)
        df.to_csv(FILENAME, index=False, encoding='utf-8-sig')
        
        print("=" * 70)
        print(f"✅ TEST COMPLETE!")
        print(f"📁 Results saved: {FILENAME}")
        print("=" * 70)
        
        # Analysis
        print("\n📊 DETECTION ANALYSIS:")
        print(f"  - Total tested: {len(df)}")
        print(f"  - Successfully detected: {len(df[df['property_type'] != 'Unknown'])}")
        print(f"  - Unknown: {len(df[df['property_type'] == 'Unknown'])}")
        print(f"\n  Type breakdown:")
        print(df['property_type'].value_counts().to_string())
        print(f"\n  Detection methods used:")
        print(df['detection_method'].value_counts().to_string())
        
        print("\n📋 SAMPLE RESULTS:")
        print(df[['property_name', 'property_type', 'detection_method']].head(10).to_string())

    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    finally:
        print("\n🔒 Closing browser...")
        driver.quit()


if __name__ == "__main__":
    main()
