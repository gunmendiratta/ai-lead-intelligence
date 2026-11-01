"""
Comprehensive Google Maps Contact Scraper for Non-Hotel Properties
Extracts detailed contact information including phone, website, address, plus code, check-in times, etc.
"""

import csv
import time
import random
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options


class GoogleMapsContactScraper:
    def __init__(self, headless=False):
        """Initialize the scraper with Chrome driver"""
        self.options = Options()
        if headless:
            self.options.add_argument('--headless')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-blink-features=AutomationControlled')
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.options.add_experimental_option('useAutomationExtension', False)
        self.options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        self.options.add_argument('--window-size=1920,1080')
        
        self.driver = None
        
    def start_driver(self):
        """Start the Chrome driver"""
        self.driver = webdriver.Chrome(options=self.options)
        
    def close_driver(self):
        """Close the Chrome driver"""
        if self.driver:
            self.driver.quit()
            
    def search_on_google_maps(self, property_name, address, street_address="", city=""):
        """
        Search for a property on Google Maps with multiple strategies
        Returns True if found, False otherwise
        """
        try:
            # Create multiple search strategies
            search_strategies = [
                f"{property_name}, {address}",
                f"{property_name}, {street_address}, {city}",
                f"{street_address}, {city}",
                property_name,
                street_address,
            ]
            
            # Remove empty strategies
            search_strategies = [s for s in search_strategies if s.strip().strip(',')]
            
            for idx, search_query in enumerate(search_strategies):
                if idx > 0:
                    print(f"  → Retry {idx}: {search_query[:60]}...")
                else:
                    print(f"  Searching: {search_query[:80]}...")
                    
                search_url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
                self.driver.get(search_url)
                
                # Wait for page to load
                time.sleep(random.uniform(2, 3))
                
                try:
                    # Wait for and click the first result
                    first_result = WebDriverWait(self.driver, 6).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[href*="/maps/place/"]'))
                    )
                    first_result.click()
                    time.sleep(random.uniform(2, 4))
                    print(f"  ✓ Found on Google Maps!")
                    return True
                except TimeoutException:
                    continue
            
            print(f"  ✗ Not found on Google Maps")
            return False
                
        except Exception as e:
            print(f"  Error searching: {e}")
            return False
    
    def scroll_sidebar(self):
        """Scroll the sidebar to load all information"""
        try:
            # Find the scrollable sidebar
            scrollable = self.driver.find_element(By.CSS_SELECTOR, 'div[role="main"]')
            
            # Scroll down in steps
            for _ in range(3):
                self.driver.execute_script("arguments[0].scrollTop += 400", scrollable)
                time.sleep(0.5)
                
        except Exception as e:
            print(f"  Note: Could not scroll sidebar - {e}")
            
    def extract_contact_details(self):
        """
        Extract comprehensive contact information from Google Maps
        """
        details = {
            'booking_property_name': '',  # Will be filled from original data
            'gmaps_name': '',
            'gmaps_address': '',
            'gmaps_phone': '',
            'gmaps_website': '',
            'gmaps_rating': '',
            'gmaps_reviews_count': '',
            'gmaps_category': '',
            'gmaps_plus_code': '',
            'gmaps_url': '',
            'gmaps_price_range': '',
            'gmaps_hours': '',
            'has_website': 'No',
            'has_phone': 'No',
            'status': 'SUCCESS'
        }
        
        try:
            # Get current URL
            details['gmaps_url'] = self.driver.current_url
            
            # Extract business name
            try:
                name = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.DUwDvf'))
                )
                details['gmaps_name'] = name.text.strip()
            except:
                pass
            
            # Extract rating and review count
            try:
                rating_elem = self.driver.find_element(By.CSS_SELECTOR, 'div.F7nice span[aria-hidden="true"]')
                details['gmaps_rating'] = rating_elem.text.strip()
                details['has_phone'] = 'Yes' if details['gmaps_rating'] else 'No'
            except:
                pass
            
            try:
                reviews = self.driver.find_element(By.CSS_SELECTOR, 'div.F7nice span[aria-label*="review"]')
                aria_label = reviews.get_attribute('aria-label')
                match = re.search(r'([\d,]+)\s+review', aria_label)
                if match:
                    details['gmaps_reviews_count'] = match.group(1)
            except:
                pass
            
            # Extract category
            try:
                category = self.driver.find_element(By.CSS_SELECTOR, 'button.DkEaL')
                details['gmaps_category'] = category.text.strip()
            except:
                pass
            
            # Scroll to load more info
            self.scroll_sidebar()
            time.sleep(1)
            
            # Extract all information from buttons
            try:
                # Get all clickable info buttons
                info_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'button[data-item-id]')
                
                for button in info_buttons:
                    try:
                        item_id = button.get_attribute('data-item-id') or ''
                        aria_label = button.get_attribute('aria-label') or ''
                        
                        # Extract address
                        if 'address' in item_id.lower():
                            try:
                                addr_div = button.find_element(By.CSS_SELECTOR, 'div.Io6YTe')
                                details['gmaps_address'] = addr_div.text.strip()
                            except:
                                if 'Address:' in aria_label:
                                    details['gmaps_address'] = aria_label.replace('Address:', '').strip()
                        
                        # Extract phone
                        elif 'phone' in item_id.lower():
                            try:
                                phone_div = button.find_element(By.CSS_SELECTOR, 'div.Io6YTe')
                                details['gmaps_phone'] = phone_div.text.strip()
                                details['has_phone'] = 'Yes'
                            except:
                                if 'Phone:' in aria_label:
                                    details['gmaps_phone'] = aria_label.replace('Phone:', '').strip()
                                    details['has_phone'] = 'Yes'
                        
                        # Extract plus code
                        elif 'oloc' in item_id.lower() or 'plus code' in aria_label.lower():
                            try:
                                plus_div = button.find_element(By.CSS_SELECTOR, 'div.Io6YTe')
                                details['gmaps_plus_code'] = plus_div.text.strip()
                            except:
                                pass
                        
                        # Extract hours
                        elif 'hours' in item_id.lower() or 'oh' in item_id.lower():
                            if aria_label:
                                details['gmaps_hours'] = aria_label.strip()
                                
                    except Exception as e:
                        continue
                        
            except Exception as e:
                print(f"  Note: Error extracting buttons - {e}")
            
            # Extract website - multiple methods
            try:
                # Method 1: Look for website button
                website_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'a[data-item-id*="authority"]')
                for btn in website_buttons:
                    href = btn.get_attribute('href')
                    if href and 'google.com' not in href and 'maps' not in href:
                        details['gmaps_website'] = href
                        details['has_website'] = 'Yes'
                        break
                
                # Method 2: Look in aria-labels
                if not details['gmaps_website']:
                    website_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[aria-label*="Website"]')
                    for link in website_links:
                        href = link.get_attribute('href')
                        if href and 'google.com' not in href:
                            details['gmaps_website'] = href
                            details['has_website'] = 'Yes'
                            break
                
                # Method 3: Look for any external links
                if not details['gmaps_website']:
                    all_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href^="http"]')
                    for link in all_links:
                        href = link.get_attribute('href')
                        text = link.text.lower()
                        if href and 'google' not in href and 'maps' not in href and ('www' in href or '.com' in href or '.ch' in href):
                            details['gmaps_website'] = href
                            details['has_website'] = 'Yes'
                            break
                            
            except Exception as e:
                print(f"  Note: Could not extract website - {e}")
            
            # Try to find phone using alternative selectors
            if not details['gmaps_phone']:
                try:
                    phone_patterns = [
                        'button[aria-label*="Phone"]',
                        'button[data-tooltip*="+"]',
                        'div.Io6YTe'
                    ]
                    for pattern in phone_patterns:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, pattern)
                        for elem in elements:
                            text = elem.text.strip()
                            # Check if it looks like a phone number
                            if re.search(r'[+]?[\d\s\-()]{8,}', text):
                                details['gmaps_phone'] = text
                                details['has_phone'] = 'Yes'
                                break
                        if details['gmaps_phone']:
                            break
                except:
                    pass
            
            print(f"  ✓ Extracted: {details['gmaps_name']}")
            if details['gmaps_phone']:
                print(f"    📞 Phone: {details['gmaps_phone']}")
            if details['gmaps_website']:
                print(f"    🌐 Website: {details['gmaps_website'][:50]}...")
            if details['gmaps_address']:
                print(f"    📍 Address: {details['gmaps_address'][:50]}...")
                
            return details
            
        except Exception as e:
            print(f"  Error extracting details: {e}")
            details['status'] = f'ERROR: {str(e)[:50]}'
            return details
    
    def scrape_property(self, property_data):
        """
        Main method to scrape a single property
        """
        property_name = property_data.get('property_name', '')
        full_address = property_data.get('full_address', '')
        street_address = property_data.get('street_address', '')
        city = property_data.get('city', '')
        
        if self.search_on_google_maps(property_name, full_address, street_address, city):
            details = self.extract_contact_details()
            details['booking_property_name'] = property_name
            return details
        else:
            return {
                'booking_property_name': property_name,
                'gmaps_name': '',
                'gmaps_address': '',
                'gmaps_phone': '',
                'gmaps_website': '',
                'gmaps_rating': '',
                'gmaps_reviews_count': '',
                'gmaps_category': '',
                'gmaps_plus_code': '',
                'gmaps_url': '',
                'gmaps_price_range': '',
                'gmaps_hours': '',
                'has_website': 'No',
                'has_phone': 'No',
                'status': 'NOT_FOUND'
            }


def load_properties_from_csv(input_file, limit=None):
    """Load non-hotel properties from CSV"""
    properties = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if limit and idx >= limit:
                break
            properties.append(row)
    
    print(f"Loaded {len(properties)} properties from {input_file}")
    return properties


def save_to_csv(original_data, gmaps_data, output_file):
    """Save combined data to CSV"""
    if not original_data or not gmaps_data:
        print("No data to save")
        return
    
    combined_data = []
    for orig, gmaps in zip(original_data, gmaps_data):
        combined = {**orig, **gmaps}
        combined_data.append(combined)
    
    # Get all fieldnames
    fieldnames = list(combined_data[0].keys())
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(combined_data)
    
    print(f"\n✓ Saved {len(combined_data)} properties to {output_file}")
    
    # Print statistics
    found_count = sum(1 for d in gmaps_data if d['status'] == 'SUCCESS')
    has_phone = sum(1 for d in gmaps_data if d['has_phone'] == 'Yes')
    has_website = sum(1 for d in gmaps_data if d['has_website'] == 'Yes')
    
    print(f"\n📊 Statistics:")
    print(f"  ✓ Found on Google Maps: {found_count}/{len(gmaps_data)}")
    print(f"  📞 Properties with phone: {has_phone}")
    print(f"  🌐 Properties with website: {has_website}")


def main(limit=None):
    """Main execution function"""
    input_file = 'property_booking_non_hotels.csv'
    output_file = 'property_booking_gmaps_contacts.csv'
    
    # Load properties
    properties = load_properties_from_csv(input_file, limit=limit)
    
    if not properties:
        print("No properties to scrape!")
        return
    
    # Initialize scraper
    scraper = GoogleMapsContactScraper(headless=False)
    scraper.start_driver()
    
    gmaps_data = []
    
    try:
        for idx, property_data in enumerate(properties, 1):
            print(f"\n{'='*80}")
            print(f"[{idx}/{len(properties)}] {property_data['property_name']}")
            print(f"{'='*80}")
            
            # Scrape Google Maps
            gmaps_info = scraper.scrape_property(property_data)
            gmaps_data.append(gmaps_info)
            
            # Save progress every 10 properties
            if idx % 10 == 0:
                save_to_csv(properties[:idx], gmaps_data, output_file)
                print(f"\n💾 Progress saved at {idx} properties")
            
            # Random delay
            time.sleep(random.uniform(1.5, 2.5))
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Scraping interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during scraping: {e}")
    finally:
        # Save final results
        save_to_csv(properties, gmaps_data, output_file)
        scraper.close_driver()
        print("\n" + "="*80)
        print(f"🎉 Scraping completed!")
        print("="*80)


if __name__ == "__main__":
    # Run for 10 properties first (testing)
    print("🧪 TESTING MODE: Running for first 10 properties\n")
    main(limit=10)
