import pandas as pd
import os
from dotenv import load_dotenv
from src.parser import CourierSheetParser
from src.logic import PricingCalculator
from src.drive_uploader import get_or_create_folder, upload_with_versioning

def load_sheet_mapping(mapping_file_path: str) -> pd.DataFrame:
    try:
        return pd.read_excel(mapping_file_path)
    except Exception as e:
        print(f"Error loading mapping file: {e}")
        return pd.DataFrame()

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
    
    if not couriers:
        print("No courier data found.")
        return

    calculator = PricingCalculator(max_weight_grams=50000, step_grams=500)
    
    # Create Excel Writer
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        has_data = False
        for courier in couriers:
            print(f"Processing Courier: {courier.name}")
            
            # Group zones by Mode
            zones_by_mode = {}
            for zone in courier.zones:
                if zone.mode not in zones_by_mode:
                    zones_by_mode[zone.mode] = []
                zones_by_mode[zone.mode].append(zone)
            
            for mode, zones in zones_by_mode.items():
                print(f"  Generating sheet for Mode: {mode}")
                
                # Combine all zones for this mode into one DataFrame
                mode_df = pd.DataFrame()
                
                for zone in zones:
                    zone_df = calculator.generate_output_dataframe(zone)
                    mode_df = pd.concat([mode_df, zone_df], ignore_index=True)
                
                if not mode_df.empty:
                    # Find mapped sheet names
                    sheet_names = []
                    if not mapping_df.empty:
                        # Filter mapping
                        matches = mapping_df[
                            (mapping_df['Sheet Name'].str.contains(courier.name, case=False, na=False)) & 
                            (mapping_df['Mode'].str.lower() == mode.lower())
                        ]
                        
                        if not matches.empty:
                            sheet_names = matches['Sheet Name'].tolist()
                    
                    if not sheet_names:
                        # Fallback
                        fallback_name = f"{courier.name}_{mode}"
                        clean_name = "".join([c for c in fallback_name if c.isalnum() or c in ['_', ' ']])
                        sheet_names = [clean_name]
                        print(f"    No mapping found for {courier.name} - {mode}. Using default: {clean_name}")
                    
                    for sheet_name in sheet_names:
                        final_sheet_name = sheet_name[:31]
                        print(f"    Writing sheet: {final_sheet_name}")
                        mode_df.to_excel(writer, sheet_name=final_sheet_name, index=False)
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
