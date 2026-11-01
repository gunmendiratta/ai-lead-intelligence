import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import pandas as pd
import traceback

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
INPUT_CSV = "/Users/varun/Desktop/all_apartments_combined_unique.csv"
OUTPUT_CSV = "/Users/varun/Desktop/apartments_with_full_details.csv"
BATCH_SIZE = 50  # Save progress every 50 properties
MAX_RETRIES = 2

# ==========================================
# 🔍 SCRAPER FUNCTIONS
# ==========================================

def extract_property_details(driver, url):
    """Extract full address and management company from property page"""
    details = {
        "full_address": "",
        "street_address": "",
        "city": "",
        "postal_code": "",
        "country": "",
        "managed_by": "",
        "property_type": "",
        "error": ""
    }
    
    try:
        driver.get(url)
        time.sleep(4)  # Wait for page load
        
        # ============ EXTRACT ADDRESS ============
        try:
            import re
            import json
            
            # METHOD 1: Extract from JSON-LD in page source
            page_source = driver.page_source
            
            # Look for address in JSON-LD structured data
            json_ld_pattern = r'"address"\s*:\s*{([^}]+)}'
            matches = re.findall(json_ld_pattern, page_source, re.IGNORECASE)
            
            for match in matches:
                # Extract streetaddress if present
                street_match = re.search(r'"streetaddress"\s*:\s*"([^"]+)"', match, re.IGNORECASE)
                postal_match = re.search(r'"postalcode"\s*:\s*"([^"]+)"', match, re.IGNORECASE)
                locality_match = re.search(r'"addresslocality"\s*:\s*"([^"]+)"', match, re.IGNORECASE)
                
                if street_match:
                    details["full_address"] = street_match.group(1).strip()
                    # Clean up if it has extra info
                    if details["full_address"]:
                        # Extract components
                        parts = details["full_address"].split(',')
                        if len(parts) >= 1:
                            details["street_address"] = parts[0].strip()
                        if postal_match:
                            details["postal_code"] = postal_match.group(1).strip()
                        if len(parts) >= 2:
                            # Try to extract city from address parts
                            for part in parts:
                                part = part.strip()
                                # Look for pattern like "3013 Bern"
                                city_match = re.search(r'\d{4}\s+(.+)', part)
                                if city_match:
                                    details["city"] = city_match.group(1).strip()
                                    if not details["postal_code"]:
                                        postal_in_part = re.search(r'(\d{4})', part)
                                        if postal_in_part:
                                            details["postal_code"] = postal_in_part.group(1)
                                    break
                        details["country"] = "Switzerland"
                        break
            
            # METHOD 2: If not found in JSON, look in visible page text
            if not details["full_address"]:
                body_text = driver.find_element(By.TAG_NAME, "body").text
                lines = body_text.split('\n')
                
                # Look for Swiss address pattern: "Street number, PostalCode City, Switzerland"
                # or with district: "Street number, District, PostalCode City, Switzerland"
                for i, line in enumerate(lines[:100]):  # Check first 100 lines
                    line = line.strip()
                    # Swiss postal codes are 4 digits
                    if re.search(r'\d{4}\s+\w+', line) and ('Switzerland' in lines[i+1:i+3] if i+1 < len(lines) else False or 'Switzerland' in line):
                        # This might be an address
                        potential_address = line
                        # Check if next line is "Switzerland" and combine
                        if i+1 < len(lines) and 'Switzerland' in lines[i+1]:
                            potential_address = line + ', ' + lines[i+1].strip()
                        elif 'Switzerland' in line:
                            potential_address = line
                        
                        # Validate it looks like an address (has street name)
                        if len(potential_address) > 10 and len(potential_address) < 200:
                            details["full_address"] = potential_address
                            # Parse components
                            parts = potential_address.split(',')
                            if len(parts) >= 1:
                                details["street_address"] = parts[0].strip()
                            # Extract postal code and city
                            postal_city_match = re.search(r'(\d{4})\s+([^,]+)', potential_address)
                            if postal_city_match:
                                details["postal_code"] = postal_city_match.group(1)
                                details["city"] = postal_city_match.group(2).strip()
                            details["country"] = "Switzerland"
                            break
        
        except Exception as e:
            details["error"] += f"Address error: {str(e)}; "
        
        # ============ EXTRACT PROPERTY TYPE ============
        try:
            # Look for property type in page text - usually near the property name
            body_text = driver.find_element(By.TAG_NAME, "body").text
            lines = body_text.split('\n')
            
            # Common property type indicators
            property_types = [
                'Hotel', 'Apartment', 'Aparthotel', 'Guest house', 
                'Bed and Breakfast', 'Hostel', 'Resort', 'Villa',
                'Chalet', 'Holiday home', 'Serviced apartment',
                'Motel', 'Inn', 'Lodge', 'Camping', 'Glamping'
            ]
            
            # Check first 30 lines for property type (usually near top)
            for i, line in enumerate(lines[:30]):
                line_stripped = line.strip()
                # Look for pattern like "PropertyName (Type) (Country)"
                if '(' in line_stripped and ')' in line_stripped:
                    # Extract content in parentheses
                    parens_content = re.findall(r'\(([^)]+)\)', line_stripped)
                    for content in parens_content:
                        for ptype in property_types:
                            if ptype.lower() in content.lower():
                                details["property_type"] = content.strip()
                                break
                        if details["property_type"]:
                            break
                
                # Also check if line itself is a property type
                if not details["property_type"]:
                    for ptype in property_types:
                        if line_stripped.lower() == ptype.lower():
                            details["property_type"] = line_stripped
                            break
                
                if details["property_type"]:
                    break
            
            # Fallback: Look in page source for property type in JSON
            if not details["property_type"]:
                page_source_lower = driver.page_source.lower()
                type_pattern = r'"@type"\s*:\s*"([^"]*)"'
                type_matches = re.findall(type_pattern, page_source_lower)
                for match in type_matches:
                    if any(pt.lower() in match for pt in property_types):
                        details["property_type"] = match.title()
                        break
        
        except Exception as e:
            details["error"] += f"Type error: {str(e)}; "
        
        # ============ EXTRACT MANAGEMENT COMPANY ============
        try:
            # Look for "Managed by" or similar patterns
            managed_patterns = [
                "managed by",
                "operated by",
                "property management",
                "management company",
                "hosted by"
            ]
            
            # Check in various sections
            page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            
            for pattern in managed_patterns:
                if pattern in page_text:
                    # Find the line containing the pattern
                    lines = page_text.split('\n')
                    for i, line in enumerate(lines):
                        if pattern in line.lower():
                            # Extract text after pattern
                            company = line.split(pattern)[-1].strip()
                            if company and len(company) < 100:  # Reasonable length
                                details["managed_by"] = company
                                break
                    if details["managed_by"]:
                        break
            
            # Alternative: Check for "by" in property name
            if not details["managed_by"]:
                try:
                    # Look for chain/brand names in header
                    header_selectors = [
                        '[data-testid="property-header-name"]',
                        '.hp__hotel-name',
                        'h1'
                    ]
                    
                    for selector in header_selectors:
                        try:
                            elem = driver.find_element(By.CSS_SELECTOR, selector)
                            text = elem.text.strip()
                            
                            # Check if it contains "by" which often indicates management
                            if " by " in text.lower():
                                parts = text.split(" by ")
                                if len(parts) > 1:
                                    details["managed_by"] = parts[-1].strip()
                                    break
                        except:
                            continue
                except:
                    pass
        
        except Exception as e:
            details["error"] += f"Managed_by error: {str(e)}; "
        
    except Exception as e:
        details["error"] = f"Page load error: {str(e)}"
    
    return details


# ==========================================
# 🚀 MAIN SCRAPER
# ==========================================

def main():
    print("=" * 80)
    print("🏠 COMPREHENSIVE PROPERTY DETAILS SCRAPER")
    print("=" * 80)
    
    # Load input CSV
    print(f"\n📂 Loading: {INPUT_CSV}")
    df = pd.read_csv(INPUT_CSV, encoding='utf-8-sig')
    print(f"✅ Loaded {len(df)} properties")
    
    # Add new columns if they don't exist
    new_columns = ["full_address", "street_address", "city", "postal_code", 
                   "country", "managed_by", "property_type", "scrape_error"]
    
    for col in new_columns:
        if col not in df.columns:
            df[col] = ""
    
    # Initialize Chrome
    print("\n🌐 Starting Chrome browser...")
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    
    try:
        # Handle cookies once
        print("🍪 Handling cookies...")
        driver.get("https://www.booking.com")
        time.sleep(3)
        try:
            driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
            time.sleep(1)
        except:
            pass
        
        # Scrape each property
        start_time = time.time()
        successful = 0
        failed = 0
        
        for idx, row in df.iterrows():
            url = row['booking_url']
            property_name = row['property_name'] if 'property_name' in row else f"Property {idx+1}"
            
            print(f"\n[{idx+1}/{len(df)}] {property_name[:60]}")
            print(f"  🔗 {url[:80]}")
            
            retry_count = 0
            while retry_count < MAX_RETRIES:
                try:
                    details = extract_property_details(driver, url)
                    
                    # Update dataframe
                    df.at[idx, 'full_address'] = details['full_address']
                    df.at[idx, 'street_address'] = details['street_address']
                    df.at[idx, 'city'] = details['city']
                    df.at[idx, 'postal_code'] = details['postal_code']
                    df.at[idx, 'country'] = details['country']
                    df.at[idx, 'managed_by'] = details['managed_by']
                    df.at[idx, 'property_type'] = details['property_type']
                    df.at[idx, 'scrape_error'] = details['error']
                    
                    # Print results
                    if details['full_address']:
                        print(f"  ✅ Address: {details['full_address']}")
                    if details['managed_by']:
                        print(f"  🏢 Managed by: {details['managed_by']}")
                    if details['property_type']:
                        print(f"  🏠 Type: {details['property_type']}")
                    if details['error']:
                        print(f"  ⚠️ Errors: {details['error']}")
                    
                    successful += 1
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    retry_count += 1
                    if retry_count < MAX_RETRIES:
                        print(f"  ⚠️ Error, retrying ({retry_count}/{MAX_RETRIES})...")
                        time.sleep(2)
                    else:
                        print(f"  ❌ Failed after {MAX_RETRIES} retries: {str(e)}")
                        df.at[idx, 'scrape_error'] = f"Failed: {str(e)}"
                        failed += 1
            
            # Save progress every BATCH_SIZE properties
            if (idx + 1) % BATCH_SIZE == 0:
                print(f"\n💾 Saving progress... ({idx+1} properties processed)")
                df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
                
                # Calculate ETA
                elapsed = time.time() - start_time
                avg_time_per_property = elapsed / (idx + 1)
                remaining = len(df) - (idx + 1)
                eta_seconds = remaining * avg_time_per_property
                eta_minutes = eta_seconds / 60
                print(f"  ⏱️ ETA: {eta_minutes:.1f} minutes")
            
            time.sleep(1)  # Be nice to the server
        
        # Final save
        print(f"\n💾 Saving final results...")
        df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
        
        # Statistics
        elapsed = time.time() - start_time
        print("\n" + "=" * 80)
        print("✅ SCRAPING COMPLETE!")
        print("=" * 80)
        print(f"📁 Output: {OUTPUT_CSV}")
        print(f"⏱️ Time: {elapsed/60:.1f} minutes")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"📊 Success rate: {successful/len(df)*100:.1f}%")
        
        # Show sample with details
        print("\n📋 SAMPLE PROPERTIES WITH DETAILS:")
        sample_df = df[df['full_address'] != ''].head(5)
        for idx, row in sample_df.iterrows():
            print(f"\n  {row['property_name']}")
            print(f"    📍 {row['full_address']}")
            if row['managed_by']:
                print(f"    🏢 {row['managed_by']}")
    
    except Exception as e:
        print(f"\n❌ Critical error: {e}")
        traceback.print_exc()
        
        # Save whatever we got
        print("\n💾 Saving partial results...")
        df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
    
    finally:
        print("\n🔒 Closing browser...")
        driver.quit()


if __name__ == "__main__":
    main()
