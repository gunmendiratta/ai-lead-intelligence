import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import pandas as pd
import re

INPUT_CSV = "/Users/varun/Desktop/all_apartments_combined_unique.csv"

def extract_property_details(driver, url):
    """Extract full address, property type, and management company"""
    details = {
        "full_address": "",
        "street_address": "",
        "city": "",
        "postal_code": "",
        "country": "",
        "managed_by": "",
        "property_type": ""
    }
    
    try:
        driver.get(url)
        time.sleep(4)
        
        # ============ EXTRACT ADDRESS FROM JSON ============
        page_source = driver.page_source
        json_ld_pattern = r'"address"\s*:\s*{([^}]+)}'
        matches = re.findall(json_ld_pattern, page_source, re.IGNORECASE)
        
        for match in matches:
            street_match = re.search(r'"streetaddress"\s*:\s*"([^"]+)"', match, re.IGNORECASE)
            postal_match = re.search(r'"postalcode"\s*:\s*"([^"]+)"', match, re.IGNORECASE)
            
            if street_match:
                details["full_address"] = street_match.group(1).strip()
                parts = details["full_address"].split(',')
                if len(parts) >= 1:
                    details["street_address"] = parts[0].strip()
                if postal_match:
                    details["postal_code"] = postal_match.group(1).strip()
                for part in parts:
                    part = part.strip()
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
        
        # ============ EXTRACT PROPERTY TYPE ============
        body_text = driver.find_element(By.TAG_NAME, "body").text
        lines = body_text.split('\n')
        
        property_types = [
            'Hotel', 'Apartment', 'Aparthotel', 'Guest house', 
            'Bed and Breakfast', 'Hostel', 'Resort', 'Villa',
            'Chalet', 'Holiday home', 'Serviced apartment',
            'Motel', 'Inn', 'Lodge', 'Camping', 'Glamping'
        ]
        
        # Check first 30 lines for property type
        for i, line in enumerate(lines[:30]):
            line_stripped = line.strip()
            # Look for pattern like "PropertyName (Type) (Country)"
            if '(' in line_stripped and ')' in line_stripped:
                parens_content = re.findall(r'\(([^)]+)\)', line_stripped)
                for content in parens_content:
                    for ptype in property_types:
                        if ptype.lower() in content.lower():
                            details["property_type"] = content.strip()
                            break
                    if details["property_type"]:
                        break
            
            if details["property_type"]:
                break
        
        # ============ EXTRACT MANAGEMENT COMPANY ============
        page_text = body_text.lower()
        
        if "managed by" in page_text:
            lines_lower = page_text.split('\n')
            for line in lines_lower:
                if "managed by" in line:
                    company = line.split("managed by")[-1].strip()
                    if company and len(company) < 100:
                        details["managed_by"] = company
                        break
    
    except Exception as e:
        pass
    
    return details

def main():
    print("=" * 80)
    print("🧪 TESTING COMPREHENSIVE EXTRACTION - 5 PROPERTIES")
    print("=" * 80)
    
    df = pd.read_csv(INPUT_CSV, encoding='utf-8-sig')
    test_df = df.head(5)
    
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    
    try:
        driver.get("https://www.booking.com")
        time.sleep(3)
        try:
            driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
            time.sleep(1)
        except:
            pass
        
        results = []
        
        for idx, row in test_df.iterrows():
            url = row['booking_url']
            property_name = row['property_name'] if 'property_name' in row else f"Property {idx+1}"
            
            print(f"\n{'='*80}")
            print(f"[{idx+1}/5] {property_name}")
            print(f"{'='*80}")
            
            details = extract_property_details(driver, url)
            
            print(f"📍 Full Address: {details['full_address'] or '❌ NOT FOUND'}")
            print(f"   └─ Street: {details['street_address']}")
            print(f"   └─ Postal: {details['postal_code']}")
            print(f"   └─ City: {details['city']}")
            print(f"🏢 Property Type: {details['property_type'] or '❌ NOT FOUND'}")
            print(f"🏢 Managed By: {details['managed_by'] or '—'}")
            
            results.append(details)
            time.sleep(1)
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        
        address_found = sum(1 for r in results if r['full_address'])
        type_found = sum(1 for r in results if r['property_type'])
        managed_found = sum(1 for r in results if r['managed_by'])
        
        print(f"✅ Address extracted: {address_found}/5 ({address_found/5*100:.0f}%)")
        print(f"✅ Property Type extracted: {type_found}/5 ({type_found/5*100:.0f}%)")
        print(f"✅ Management info extracted: {managed_found}/5 ({managed_found/5*100:.0f}%)")
        
        print("\n🏢 Property Types Found:")
        for i, r in enumerate(results, 1):
            if r['property_type']:
                print(f"  {i}. {r['property_type']}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
