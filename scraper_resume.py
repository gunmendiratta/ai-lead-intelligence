import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import pandas as pd
import re
import traceback

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
INPUT_CSV = "/Users/varun/Desktop/all_apartments_combined_unique.csv"
OUTPUT_CSV = "/Users/varun/Desktop/apartments_with_full_details.csv"
EXISTING_CSV = OUTPUT_CSV  # Resume from this file
BATCH_SIZE = 50
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
        time.sleep(4)
        
        # ============ EXTRACT ADDRESS ============
        try:
            page_source = driver.page_source
            
            # Extract from JSON-LD
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
            
        except Exception as e:
            details["error"] += f"Address error: {str(e)}; "
        
        # ============ EXTRACT PROPERTY TYPE ============
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            lines = body_text.split('\n')
            
            property_types = [
                'Hotel', 'Apartment', 'Aparthotel', 'Guest house', 
                'Bed and Breakfast', 'Hostel', 'Resort', 'Villa',
                'Chalet', 'Holiday home', 'Serviced apartment',
                'Motel', 'Inn', 'Lodge', 'Camping', 'Glamping'
            ]
            
            for i, line in enumerate(lines[:30]):
                line_stripped = line.strip()
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
        
        except Exception as e:
            details["error"] += f"Type error: {str(e)}; "
        
        # ============ EXTRACT MANAGEMENT COMPANY ============
        try:
            page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            
            if "managed by" in page_text:
                lines = page_text.split('\n')
                for line in lines:
                    if "managed by" in line:
                        company = line.split("managed by")[-1].strip()
                        if company and len(company) < 100:
                            details["managed_by"] = company
                            break
        
        except Exception as e:
            details["error"] += f"Managed_by error: {str(e)}; "
    
    except Exception as e:
        details["error"] = f"Page load error: {str(e)}"
    
    return details


# ==========================================
# 🚀 MAIN SCRAPER - RESUME MODE
# ==========================================

def main():
    print("=" * 80)
    print("🏠 COMPREHENSIVE PROPERTY DETAILS SCRAPER - RESUME MODE")
    print("=" * 80)
    
    # Load input CSV
    print(f"\n📂 Loading: {INPUT_CSV}")
    df_input = pd.read_csv(INPUT_CSV, encoding='utf-8-sig')
    print(f"✅ Total properties to scrape: {len(df_input)}")
    
    # Load existing CSV to see how many were already scraped
    print(f"\n📂 Loading existing results: {EXISTING_CSV}")
    try:
        df_existing = pd.read_csv(EXISTING_CSV, encoding='utf-8-sig')
        start_idx = len(df_existing)
        print(f"✅ Already scraped: {start_idx} properties")
    except:
        df_existing = pd.DataFrame()
        start_idx = 0
        print(f"⚠️ No existing file found, starting from beginning")
    
    print(f"🎯 Resuming from property {start_idx + 1}\n")
    
    # Initialize Chrome
    print("🌐 Starting Chrome browser...")
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    
    try:
        # Handle cookies
        print("🍪 Handling cookies...")
        driver.get("https://www.booking.com")
        time.sleep(3)
        try:
            driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
            time.sleep(1)
        except:
            pass
        
        # Scrape remaining properties
        start_time = time.time()
        successful = 0
        failed = 0
        
        results_buffer = []
        
        for idx in range(start_idx, len(df_input)):
            row = df_input.iloc[idx]
            url = row['booking_url']
            property_name = row['property_name'] if 'property_name' in row else f"Property {idx+1}"
            
            print(f"[{idx+1}/{len(df_input)}] {property_name[:60]}", end=" | ")
            
            retry_count = 0
            while retry_count < MAX_RETRIES:
                try:
                    details = extract_property_details(driver, url)
                    
                    # Create result row
                    result_row = {
                        "property_name": row['property_name'] if 'property_name' in row else "",
                        "booking_url": url,
                        "full_address": details['full_address'],
                        "street_address": details['street_address'],
                        "postal_code": details['postal_code'],
                        "city": details['city'],
                        "country": details['country'],
                        "managed_by": details['managed_by'],
                        "property_type": details['property_type'],
                        "scrape_error": details['error']
                    }
                    
                    # Add optional columns if present
                    if 'city' in row:
                        result_row['city_search'] = row['city']
                    
                    results_buffer.append(result_row)
                    
                    # Print summary
                    status = []
                    if details['full_address']:
                        status.append("📍")
                    if details['property_type']:
                        status.append(f"({details['property_type']})")
                    if details['managed_by']:
                        status.append(f"🏢")
                    
                    print("✅ " + " ".join(status))
                    successful += 1
                    break
                    
                except Exception as e:
                    retry_count += 1
                    if retry_count < MAX_RETRIES:
                        print(f"⚠️ Retry {retry_count}...", end="")
                        time.sleep(2)
                    else:
                        print(f"❌ Failed")
                        failed += 1
            
            # Save progress every BATCH_SIZE properties
            if (idx + 1 - start_idx) % BATCH_SIZE == 0:
                print(f"\n💾 Saving progress ({idx + 1}/{len(df_input)})...")
                
                # Combine existing and new results
                if len(df_existing) > 0:
                    df_new = pd.DataFrame(results_buffer)
                    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                else:
                    df_combined = pd.DataFrame(results_buffer)
                
                df_combined.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
                
                # Calculate ETA
                elapsed = time.time() - start_time
                avg_time = elapsed / ((idx + 1) - start_idx)
                remaining = len(df_input) - (idx + 1)
                eta_seconds = remaining * avg_time
                eta_minutes = eta_seconds / 60
                print(f"  ⏱️  ETA: {eta_minutes:.1f} minutes\n")
                
                # Reset buffer and existing df
                results_buffer = []
                df_existing = df_combined
        
        # Final save
        print(f"\n💾 Saving final results...")
        if len(df_existing) > 0:
            df_new = pd.DataFrame(results_buffer)
            df_final = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df_final = pd.DataFrame(results_buffer)
        
        df_final.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
        
        # Statistics
        elapsed = time.time() - start_time
        print("\n" + "=" * 80)
        print("✅ SCRAPING COMPLETE!")
        print("=" * 80)
        print(f"📁 Output: {OUTPUT_CSV}")
        print(f"⏱️  Time: {elapsed/60:.1f} minutes")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        if successful > 0:
            print(f"📊 Success rate: {successful/(successful+failed)*100:.1f}%")
        
        print(f"\n📊 Total properties with data:")
        print(f"  ✅ With address: {len(df_final[df_final['full_address'] != ''])}")
        print(f"  ✅ With property type: {len(df_final[df_final['property_type'] != ''])}")
        print(f"  ✅ With management: {len(df_final[df_final['managed_by'] != ''])}")

    except Exception as e:
        print(f"\n❌ Critical error: {e}")
        traceback.print_exc()
        
        # Save whatever we got
        if len(results_buffer) > 0 or len(df_existing) > 0:
            print("\n💾 Saving partial results...")
            if len(df_existing) > 0:
                df_new = pd.DataFrame(results_buffer)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                df_combined = pd.DataFrame(results_buffer)
            df_combined.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
    
    finally:
        print("\n🔒 Closing browser...")
        driver.quit()


if __name__ == "__main__":
    main()
