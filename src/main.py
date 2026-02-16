import pandas as pd
import os
from dotenv import load_dotenv
from src.parser import CourierSheetParser
from src.logic import PricingCalculator
from src.drive_uploader import get_or_create_folder, upload_with_versioning
from src.models import ZonePricing

def load_sheet_mapping(mapping_file_path: str) -> pd.DataFrame:
    try:
        return pd.read_excel(mapping_file_path)
    except Exception as e:
        print(f"Error loading mapping file: {e}")
        return pd.DataFrame()

def create_default_zone_pricing(zone_name: str, mode: str) -> ZonePricing:
    zp = ZonePricing(zone_name=zone_name, mode=mode)
    # Globals
    zp.volumetric_coefficient = 5000.0
    zp.tax_pct = 18.0
    # No rules -> PriceEngine returns 0
    return zp

def main():
    # Load env vars
    load_dotenv()
    folder_id = os.getenv("FOLDER_ID")
    credentials_path = os.getenv("CREDENTIALS_PATH")
    
    if not folder_id or not credentials_path:
        print("Error: FOLDER_ID or CREDENTIALS_PATH not set in .env")
        return

    input_file = "D2C Pricing Base File Template (1).xlsx"
    mapping_file = "Courier_ids_Modes.xlsx"
    output_dir = "output"
    output_file = os.path.join(output_dir, "Courier_Pricing_Output.xlsx")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Load mapping
    print(f"Reading mapping file: {mapping_file}")
    mapping_df = load_sheet_mapping(mapping_file)
    if mapping_df.empty:
        print("Warning: Mapping file empty or not found. Fallback to default naming.")
        
    print(f"Reading input file: {input_file}")
    parser = CourierSheetParser(input_file)
    couriers = parser.parse()
    
    # Create map: lower(courier_name) -> CourierData
    courier_map = {c.name.lower(): c for c in couriers}
    
    if not couriers:
        print("No courier data found in input file.")
        return

    calculator = PricingCalculator(max_weight_grams=50000, step_grams=500)
    
    # Helper to check if a courier matches mapping sheet name
    def find_courier_for_sheet(sheet_name):
        sheet_lower = sheet_name.lower()
        # Sort keys by length desc to match longest first (e.g. "Delhivery" vs "Del")
        for name in sorted(courier_map.keys(), key=len, reverse=True):
            if name in sheet_lower:
                return courier_map[name]
        return None

    # Helper to clean mode
    def clean_mode_str(mode_str):
        if not isinstance(mode_str, str): return ""
        return mode_str.strip()

    # Create Excel Writer
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        has_data = False
        
        # We iterate through the mapping file rows primarily
        if not mapping_df.empty:
            for index, row in mapping_df.iterrows():
                sheet_name = str(row['Sheet Name'])
                target_mode = clean_mode_str(row['Mode']) # e.g. "Surface", "Reverse Air"
                
                # Check for Reverse
                is_reverse = "reverse" in target_mode.lower()
                
                # If Reverse: "Reverse Air" -> "Air", "Reverse" -> "Surface" (default)
                base_mode = target_mode
                if is_reverse:
                    if "air" in target_mode.lower():
                        base_mode = "Air"
                    elif "sdd" in target_mode.lower():
                        base_mode = "SDD"
                    elif "ndd" in target_mode.lower():
                        base_mode = "NDD"
                    else:
                        base_mode = "Surface" # Default for just "Reverse"
                
                courier = find_courier_for_sheet(sheet_name)
                
                mode_df = pd.DataFrame()
                zones_processed = False
                
                if courier:
                    # Look for base_mode in courier zones
                    zones = [z for z in courier.zones if z.mode.lower() == base_mode.lower()]
                    
                    if zones:
                        for zone in zones:
                            zone_df = calculator.generate_output_dataframe(zone, force_price_zero=is_reverse)
                            mode_df = pd.concat([mode_df, zone_df], ignore_index=True)
                        zones_processed = True
                    else:
                        print(f"Courier found ({courier.name}) but mode '{base_mode}' missing for sheet '{sheet_name}'. Using defaults.")
                
                if not zones_processed:
                    # Generate default/empty sheet
                    zones = ["Local", "Within State", "Metro", "Rest of India", "Special Zone"]
                    for z_name in zones:
                        dummy_zp = create_default_zone_pricing(z_name, base_mode)
                        zone_df = calculator.generate_output_dataframe(dummy_zp, force_price_zero=False) 
                        mode_df = pd.concat([mode_df, zone_df], ignore_index=True)

                if not mode_df.empty:
                    final_sheet_name = sheet_name[:31]
                    try:
                        mode_df.to_excel(writer, sheet_name=final_sheet_name, index=False)
                        has_data = True
                    except ValueError:
                        print(f"Error writing sheet: {final_sheet_name}. Skipping.")
                        pass
        else:
            # Fallback to old logic if no mapping
            print("No Courier ids/modes mapping file/data. Running default generation.")
            for courier in couriers:
                zones_by_mode = {}
                for zone in courier.zones:
                    if zone.mode not in zones_by_mode:
                        zones_by_mode[zone.mode] = []
                    zones_by_mode[zone.mode].append(zone)
                
                for mode, zones in zones_by_mode.items():
                    mode_df = pd.DataFrame()
                    for zone in zones:
                        zone_df = calculator.generate_output_dataframe(zone)
                        mode_df = pd.concat([mode_df, zone_df], ignore_index=True)
                    
                    if not mode_df.empty:
                        sheet_name = f"{courier.name}_{mode}"[:31]
                        sheet_name = "".join([c for c in sheet_name if c.isalnum() or c in ['_', ' ']])
                        mode_df.to_excel(writer, sheet_name=sheet_name, index=False)
                        has_data = True
        
        if not has_data:
            print("No output data generated.")
            return
        else:
            print(f"Output saved locally to: {output_file}")

    # Drive Upload Logic
    try:
        print("Starting Drive Upload...")
        # Folder Name from Input File (without extension)
        input_name_stem = os.path.splitext(input_file)[0]
        
        target_folder_id = get_or_create_folder(credentials_path, folder_id, input_name_stem)
        print(f"Target Drive Folder ID: {target_folder_id}")
        
        # Upload Input File
        print(f"Uploading Input File: {input_file}")
        input_link = upload_with_versioning(input_file, credentials_path, target_folder_id)
        print(f"Input File Link: {input_link}")
        
        # Upload Output File
        print(f"Uploading Output File: {output_file}")
        output_link = upload_with_versioning(output_file, credentials_path, target_folder_id)
        print(f"Output File Link: {output_link}")
        
    except Exception as e:
        print(f"Error during Drive upload: {e}")

if __name__ == "__main__":
    main()
