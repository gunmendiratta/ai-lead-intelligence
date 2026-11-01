"""
Filter Non-Hotel Properties from Booking.com CSV
Creates a new CSV with only apartments, aparthotels, and other non-hotel properties
"""

import csv

def filter_non_hotels(input_file, output_file):
    """Filter out hotels and keep only non-hotel properties"""
    non_hotels = []
    hotels_count = 0
    no_address_count = 0
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        for row in reader:
            property_type = row.get('property_type', '').strip()
            full_address = row.get('full_address', '').strip()
            
            # Skip hotels
            if property_type.lower() == 'hotel':
                hotels_count += 1
                continue
            
            # Skip entries without addresses
            if not full_address:
                no_address_count += 1
                continue
                
            non_hotels.append(row)
    
    # Save non-hotel properties
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(non_hotels)
    
    print(f"✓ Total properties processed: {hotels_count + no_address_count + len(non_hotels)}")
    print(f"  - Hotels (excluded): {hotels_count}")
    print(f"  - No address (excluded): {no_address_count}")
    print(f"  - Non-hotel properties: {len(non_hotels)}")
    print(f"\n✓ Saved {len(non_hotels)} non-hotel properties to: {output_file}")
    
    # Show property type breakdown
    type_counts = {}
    for prop in non_hotels:
        ptype = prop.get('property_type', 'Unknown').strip()
        type_counts[ptype] = type_counts.get(ptype, 0) + 1
    
    print(f"\nProperty type breakdown:")
    for ptype, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {ptype}: {count}")

if __name__ == "__main__":
    input_file = 'property_booking.csv'
    output_file = 'property_booking_non_hotels.csv'
    
    filter_non_hotels(input_file, output_file)
