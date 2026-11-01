"""
Google Maps Scraper for Non-Hotel Properties
Scrapes contact information and details from Google Maps for properties from booking.com data
"""

import csv
import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys


class GoogleMapsScraper:
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
        
        self.driver = None
        
    def start_driver(self):
        """Start the Chrome driver"""
        self.driver = webdriver.Chrome(options=self.options)
        self.driver.maximize_window()
        
    def close_driver(self):
        """Close the Chrome driver"""
        if self.driver:
            self.driver.quit()
            
    def search_on_google_maps(self, property_name, address, city):
        """
        Search for a property on Google Maps
        Returns the first result URL or None
        Tries multiple search strategies for better results
        """
        try:
            # Clean property name (remove booking.com specific terms)
            clean_name = property_name.replace('- Self Check-In', '').replace('- Online Check In', '').replace('by Homenhancement', '').strip()
            
            # Extract street address from full address
            street = address.split(',')[0].strip() if ',' in address else address
            
            # Try multiple search strategies
            search_strategies = [
                f"{clean_name}, {street}, {city}",  # Clean name with street and city
                f"{street}, {city}",  # Street and city
                f"{clean_name}, {city}",  # Just clean name and city
                address,  # Full address
                f"{property_name}, {city}",  # Original name with city
                street,  # Just street address
            ]
            
            for strategy_idx, search_query in enumerate(search_strategies):
                print(f"  Attempt {strategy_idx+1}: {search_query}")
                search_url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
                self.driver.get(search_url)
                
                # Wait for results to load
                time.sleep(random.uniform(2, 3))
                
                # Try to click on the first result
                try:
                    # Wait for the first result to be clickable
                    first_result = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[href*="/maps/place/"]'))
                    )
                    first_result.click()
                    time.sleep(random.uniform(2, 3))
                    print(f"  ✓ Found result!")
                    return True
                except TimeoutException:
                    continue
            
            print(f"  ✗ No results found")
            return False
                
        except Exception as e:
            print(f"Error searching Google Maps: {e}")
            return False
            
    def extract_property_details(self):
        """
        Extract all available details from the Google Maps property page
        """
        details = {
            'gmaps_name': '',
            'gmaps_address': '',
            'gmaps_phone': '',
            'gmaps_website': '',
            'gmaps_rating': '',
            'gmaps_total_reviews': '',
            'gmaps_category': '',
            'gmaps_plus_code': '',
            'gmaps_url': '',
            'gmaps_email': '',
            'gmaps_hours': '',
            'gmaps_price_range': '',
        }
        
        try:
            # Get current URL
            details['gmaps_url'] = self.driver.current_url
            
            # Extract property name
            try:
                name_elem = self.driver.find_element(By.CSS_SELECTOR, 'h1.DUwDvf')
                details['gmaps_name'] = name_elem.text.strip()
            except NoSuchElementException:
                pass
                
            # Extract rating
            try:
                rating_elem = self.driver.find_element(By.CSS_SELECTOR, 'div.F7nice span[aria-hidden="true"]')
                details['gmaps_rating'] = rating_elem.text.strip()
            except NoSuchElementException:
                pass
                
            # Extract total reviews
            try:
                reviews_elem = self.driver.find_element(By.CSS_SELECTOR, 'div.F7nice span[aria-label*="reviews"]')
                aria_label = reviews_elem.get_attribute('aria-label')
                # Extract number from aria-label
                import re
                match = re.search(r'([\d,]+)\s+review', aria_label)
                if match:
                    details['gmaps_total_reviews'] = match.group(1)
            except NoSuchElementException:
                pass
                
            # Extract category
            try:
                category_elem = self.driver.find_element(By.CSS_SELECTOR, 'button.DkEaL')
                details['gmaps_category'] = category_elem.text.strip()
            except NoSuchElementException:
                pass
            
            # Scroll down to load all information panels
            try:
                scrollable_div = self.driver.find_element(By.CSS_SELECTOR, 'div[role="main"]')
                for _ in range(3):
                    self.driver.execute_script("arguments[0].scrollTop += 300", scrollable_div)
                    time.sleep(0.5)
            except:
                pass
                
            # Method 1: Extract from buttons with data-item-id
            try:
                info_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'button[data-item-id]')
                
                for button in info_buttons:
                    try:
                        item_id = button.get_attribute('data-item-id')
                        aria_label = button.get_attribute('aria-label') or ''
                        
                        if not item_id:
                            continue
                            
                        # Address
                        if 'address' in item_id.lower():
                            try:
                                address_div = button.find_element(By.CSS_SELECTOR, 'div.Io6YTe')
                                details['gmaps_address'] = address_div.text.strip()
                            except:
                                if 'Address:' in aria_label:
                                    details['gmaps_address'] = aria_label.replace('Address: ', '').strip()
                                    
                        # Phone
                        elif 'phone' in item_id.lower():
                            try:
                                phone_div = button.find_element(By.CSS_SELECTOR, 'div.Io6YTe')
                                details['gmaps_phone'] = phone_div.text.strip()
                            except:
                                if 'Phone:' in aria_label:
                                    details['gmaps_phone'] = aria_label.replace('Phone: ', '').strip()
                                    
                        # Website
                        elif 'authority' in item_id.lower() or 'website' in item_id.lower():
                            href = button.get_attribute('href')
                            if href and 'google.com' not in href:
                                details['gmaps_website'] = href
                            else:
                                try:
                                    website_div = button.find_element(By.CSS_SELECTOR, 'div.Io6YTe')
                                    details['gmaps_website'] = website_div.text.strip()
                                except:
                                    pass
                                    
                        # Plus code
                        elif 'oloc' in item_id.lower():
                            try:
                                plus_div = button.find_element(By.CSS_SELECTOR, 'div.Io6YTe')
                                details['gmaps_plus_code'] = plus_div.text.strip()
                            except:
                                pass
                                
                    except Exception as e:
                        continue
            except Exception as e:
                print(f"  Warning extracting from buttons: {e}")
            
            # Method 2: Try alternative selectors for phone
            if not details['gmaps_phone']:
                try:
                    phone_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'button[aria-label*="Phone"], button[data-tooltip*="+"]')
                    for btn in phone_buttons:
                        aria = btn.get_attribute('aria-label') or ''
                        tooltip = btn.get_attribute('data-tooltip') or ''
                        
                        if 'Phone:' in aria:
                            details['gmaps_phone'] = aria.replace('Phone: ', '').strip()
                            break
                        elif '+' in tooltip:
                            details['gmaps_phone'] = tooltip.strip()
                            break
                except:
                    pass
            
            # Method 3: Try to find phone in page source
            if not details['gmaps_phone']:
                try:
                    page_source = self.driver.page_source
                    import re
                    # Look for phone patterns
                    phone_patterns = [
                        r'\+\d{1,3}\s?\d{1,4}\s?\d{1,4}\s?\d{1,4}\s?\d{1,4}',
                        r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',
                    ]
                    for pattern in phone_patterns:
                        match = re.search(pattern, page_source)
                        if match:
                            details['gmaps_phone'] = match.group(0)
                            break
                except:
                    pass
            
            # Method 4: Look for website links
            if not details['gmaps_website']:
                try:
                    website_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href^="http"]')
                    for link in website_links:
                        href = link.get_attribute('href')
                        if href and 'google.com' not in href and 'gstatic.com' not in href and 'booking.com' not in href:
                            details['gmaps_website'] = href
                            break
                except:
                    pass
                    
            # Extract opening hours
            try:
                hours_button = self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label*="Hours"], button[data-item-id*="oh"]')
                aria_label = hours_button.get_attribute('aria-label')
                if aria_label:
                    details['gmaps_hours'] = aria_label.strip()
            except:
                pass
            
            # Look for email in page source
            try:
                page_source = self.driver.page_source
                import re
                email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                emails = re.findall(email_pattern, page_source)
                if emails:
                    # Filter out common non-contact emails
                    filtered_emails = [e for e in emails if 'noreply' not in e.lower() and 'example' not in e.lower()]
                    if filtered_emails:
                        details['gmaps_email'] = filtered_emails[0]
            except:
                pass
            
            print(f"  Extracted: {details['gmaps_name']}")
            if details['gmaps_phone']:
                print(f"  Phone: {details['gmaps_phone']}")
            if details['gmaps_website']:
                print(f"  Website: {details['gmaps_website']}")
            
            return details
            
        except Exception as e:
            print(f"  Error extracting property details: {e}")
            return details
            
    def scrape_property(self, property_name, address, city):
        """
        Main method to scrape a single property
        Returns dictionary with all scraped details
        """
        if self.search_on_google_maps(property_name, address, city):
            return self.extract_property_details()
        else:
            return None


def load_properties_from_csv(input_file):
    """Load properties from the booking.com CSV, filtering out hotels"""
    properties = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Filter out hotels and entries without addresses
            property_type = row.get('property_type', '').strip().lower()
            
            # Skip if it's a hotel, inn, or if there's no address
            if property_type in ['hotel', 'inn'] or not row.get('full_address'):
                continue
                
            properties.append(row)
    
    print(f"Loaded {len(properties)} non-hotel properties from {input_file}")
    return properties


def save_to_csv(data, output_file):
    """Save scraped data to CSV"""
    if not data:
        print("No data to save")
        return
    
    # Combine original data with scraped data
    fieldnames = list(data[0].keys())
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    
    print(f"Saved {len(data)} properties to {output_file}")


def main():
    """Main execution function"""
    input_file = 'property_booking.csv'
    output_file = 'property_booking_gmaps_scraped.csv'
    
    # Load properties from CSV
    properties = load_properties_from_csv(input_file)
    
    # TESTING: Limit to first 10 properties
    properties = properties[:10]
    
    if not properties:
        print("No properties to scrape!")
        return
    
    # Initialize scraper
    scraper = GoogleMapsScraper(headless=False)  # Set to True to run in background
    scraper.start_driver()
    
    # Results storage
    scraped_data = []
    
    try:
        for idx, property_data in enumerate(properties, 1):
            print(f"\n{'='*80}")
            print(f"Processing {idx}/{len(properties)}: {property_data['property_name']}")
            print(f"Type: {property_data.get('property_type', 'N/A')}")
            print(f"{'='*80}")
            
            # Scrape Google Maps data
            gmaps_data = scraper.scrape_property(
                property_data['property_name'],
                property_data['full_address'],
                property_data.get('city', '')
            )
            
            # Combine original booking.com data with Google Maps data
            # Add unique key for easy merging later
            combined_data = {
                'booking_property_name': property_data['property_name'],  # Key for merging
                'booking_city': property_data.get('city', ''),
                'booking_address': property_data.get('full_address', ''),
                'booking_street': property_data.get('street_address', ''),
                'booking_postal_code': property_data.get('postal_code', ''),
                'booking_country': property_data.get('country', ''),
                'booking_property_type': property_data.get('property_type', ''),
                'booking_managed_by': property_data.get('managed_by', ''),
                'booking_url': property_data.get('booking_url', ''),
            }
            
            if gmaps_data:
                combined_data.update(gmaps_data)
                combined_data['scrape_status'] = 'SUCCESS'
            else:
                # Add empty Google Maps fields if scraping failed
                combined_data.update({
                    'gmaps_name': '',
                    'gmaps_address': '',
                    'gmaps_phone': '',
                    'gmaps_website': '',
                    'gmaps_rating': '',
                    'gmaps_total_reviews': '',
                    'gmaps_category': '',
                    'gmaps_plus_code': '',
                    'gmaps_url': '',
                    'gmaps_email': '',
                    'gmaps_hours': '',
                    'gmaps_price_range': '',
                    'scrape_status': 'NOT FOUND',
                })
            
            scraped_data.append(combined_data)
            
            # Save progress every 10 properties
            if idx % 10 == 0:
                save_to_csv(scraped_data, output_file)
                print(f"\n✓ Progress saved: {idx} properties processed")
            
            # Random delay to avoid being blocked
            time.sleep(random.uniform(1, 2))
            
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user")
    except Exception as e:
        print(f"\n\nError during scraping: {e}")
    finally:
        # Save final results
        save_to_csv(scraped_data, output_file)
        scraper.close_driver()
        print("\n" + "="*80)
        print(f"Scraping completed! Total properties scraped: {len(scraped_data)}")
        print(f"Results saved to: {output_file}")
        print("="*80)


if __name__ == "__main__":
    main()
