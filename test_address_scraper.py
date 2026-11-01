import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import pandas as pd

# ==========================================
# ⚙️ TEST 5 PROPERTIES
# ==========================================
INPUT_CSV = "/Users/varun/Desktop/all_apartments_combined_unique.csv"

# ==========================================
# 🔍 SCRAPER FUNCTIONS
# ==========================================

def extract_property_details(driver, url, property_name):
    """Extract full address and management company from property page"""
    print(f"\n{'='*80}")
    print(f"🏠 {property_name}")
    print(f"🔗 {url}")
    print(f"{'='*80}")
    
    details = {
        "full_address": "",
        "street_address": "",
        "city": "",
        "postal_code": "",
        "country": "",
        "managed_by": "",
        "property_type": "",
    }
    
    try:
        driver.get(url)
        time.sleep(5)  # Wait for page load
        
        print("\n📍 SEARCHING FOR ADDRESS...")
        
        # ============ METHOD 1: Look for address in page ============
        try:
            # Get all text content
            body = driver.find_element(By.TAG_NAME, "body")
            page_text = body.text
            
            # Look for common address patterns
            lines = page_text.split('\n')
            
            # Print first 100 lines to see structure
            print("\n📄 First 50 lines of page:")
            for i, line in enumerate(lines[:50]):
                if line.strip():
                    print(f"  [{i}] {line[:100]}")
            
        except Exception as e:
            print(f"  ❌ Error reading page text: {e}")
        
        # ============ METHOD 2: Try specific selectors ============
        print("\n🔍 TRYING SPECIFIC SELECTORS...")
        
        address_selectors = [
            ('data-testid="address"', By.CSS_SELECTOR, '[data-testid="address"]'),
            ('class hp_address_subtitle', By.CLASS_NAME, 'hp_address_subtitle'),
            ('class address', By.CLASS_NAME, 'address'),
            ('aria-label containing address', By.XPATH, '//*[contains(@aria-label, "address")]'),
            ('text containing street/road', By.XPATH, '//*[contains(text(), "Street") or contains(text(), "Road") or contains(text(), "strasse")]'),
        ]
        
        for name, by_type, selector in address_selectors:
            try:
                elem = driver.find_element(by_type, selector)
                text = elem.text.strip()
                if text:
                    print(f"  ✅ Found via {name}: {text}")
                    details["full_address"] = text
                    break
            except Exception as e:
                print(f"  ❌ {name}: Not found")
        
        # ============ METHOD 3: Look in page source for address ============
        print("\n🔍 SEARCHING PAGE SOURCE FOR ADDRESS PATTERNS...")
        try:
            page_source = driver.page_source.lower()
            
            # Look for address-related JSON or data attributes
            import re
            
            # Search for postal codes (Swiss format: 4 digits)
            postal_matches = re.findall(r'\b\d{4}\b', page_source)
            if postal_matches:
                print(f"  📮 Potential postal codes found: {postal_matches[:5]}")
            
            # Search for "address" in page source
            if '"address"' in page_source or "'address'" in page_source:
                print(f"  ✅ Found 'address' keyword in source")
                # Try to extract surrounding context
                idx = page_source.find('"address"')
                if idx > 0:
                    snippet = page_source[idx:idx+200]
                    print(f"  📄 Context: {snippet[:150]}")
            
        except Exception as e:
            print(f"  ❌ Error searching page source: {e}")
        
        # ============ EXTRACT MANAGEMENT COMPANY ============
        print("\n🏢 SEARCHING FOR MANAGEMENT COMPANY...")
        
        try:
            page_text_lower = driver.find_element(By.TAG_NAME, "body").text.lower()
            
            managed_patterns = [
                ("managed by", "managed by"),
                ("operated by", "operated by"),
                ("property managed", "property managed"),
                ("management:", "management:"),
            ]
            
            for pattern_name, pattern in managed_patterns:
                if pattern in page_text_lower:
                    print(f"  ✅ Found '{pattern_name}' in page")
                    # Find the line containing the pattern
                    lines = page_text_lower.split('\n')
                    for i, line in enumerate(lines):
                        if pattern in line:
                            print(f"    📄 Line: {line[:150]}")
                            # Extract company name after pattern
                            company = line.split(pattern)[-1].strip()
                            if company and len(company) < 100:
                                details["managed_by"] = company
                                print(f"    🏢 Extracted: {company}")
                            break
                    if details["managed_by"]:
                        break
            
            # Check for "by" in property name (e.g., "Apartment by CompanyName")
            if not details["managed_by"] and " by " in property_name.lower():
                parts = property_name.split(" by ")
                if len(parts) > 1:
                    details["managed_by"] = parts[-1].strip()
                    print(f"  ✅ Extracted from name: {details['managed_by']}")
        
        except Exception as e:
            print(f"  ❌ Error searching for management: {e}")
        
        # ============ PRINT SUMMARY ============
        print("\n📊 EXTRACTED DETAILS:")
        print(f"  📍 Full Address: {details['full_address'] or 'NOT FOUND'}")
        print(f"  🏢 Managed By: {details['managed_by'] or 'NOT FOUND'}")
        print(f"  🏠 Property Type: {details['property_type'] or 'NOT FOUND'}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    return details


# ==========================================
# 🚀 MAIN TEST
# ==========================================

def main():
    print("=" * 80)
    print("🧪 TESTING ADDRESS EXTRACTION - 5 PROPERTIES")
    print("=" * 80)
    
    # Load input CSV
    df = pd.read_csv(INPUT_CSV, encoding='utf-8-sig')
    print(f"\n✅ Loaded {len(df)} total properties")
    print(f"🎯 Testing first 5 properties\n")
    
    # Get first 5 properties
    test_df = df.head(5)
    
    # Initialize Chrome
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    
    results = []
    
    try:
        # Handle cookies
        driver.get("https://www.booking.com")
        time.sleep(3)
        try:
            driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
            time.sleep(1)
        except:
            pass
        
        # Test each property
        for idx, row in test_df.iterrows():
            url = row['booking_url']
            property_name = row['property_name'] if 'property_name' in row else f"Property {idx+1}"
            
            details = extract_property_details(driver, url, property_name)
            results.append({
                "property_name": property_name,
                "url": url,
                **details
            })
            
            time.sleep(2)
        
        # Print summary
        print("\n" + "=" * 80)
        print("📊 FINAL SUMMARY")
        print("=" * 80)
        
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['property_name']}")
            print(f"   Address: {result['full_address'] or '❌ NOT FOUND'}")
            print(f"   Managed: {result['managed_by'] or '❌ NOT FOUND'}")
        
        # Success rate
        address_found = sum(1 for r in results if r['full_address'])
        managed_found = sum(1 for r in results if r['managed_by'])
        
        print(f"\n✅ Address found: {address_found}/5 ({address_found/5*100:.0f}%)")
        print(f"✅ Management found: {managed_found}/5 ({managed_found/5*100:.0f}%)")
    
    finally:
        print("\n🔒 Closing browser...")
        driver.quit()


if __name__ == "__main__":
    main()
