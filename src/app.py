import os
import shutil
import tempfile
import pandas as pd
from typing import Dict, Any, List
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from src.parser import CourierSheetParser
from src.logic import PricingCalculator
from src.drive_uploader import get_or_create_folder, upload_with_versioning
from src.models import ZonePricing

# Initialize App
app = FastAPI(title="Courier Pricing Automation API")

# Load Environment Variables
load_dotenv()
FOLDER_ID = os.getenv("FOLDER_ID")
CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH")
MAPPING_FILE = os.getenv("MAPPING_FILE_PATH")

# Ensure mapping file exists
if not os.path.exists(MAPPING_FILE):
    print(f"Warning: {MAPPING_FILE} not found in root directory.")

def load_sheet_mapping(mapping_file_path: str) -> pd.DataFrame:
    try:
        if os.path.exists(mapping_file_path):
            return pd.read_excel(mapping_file_path)
        return pd.DataFrame()
    except Exception as e:
        print(f"Error loading mapping file: {e}")
        return pd.DataFrame()

def create_default_zone_pricing(zone_name: str, mode: str) -> ZonePricing:
    zp = ZonePricing(zone_name=zone_name, mode=mode)
    zp.volumetric_coefficient = 5000.0
    zp.tax_pct = 18.0
    return zp

def find_courier_for_sheet(sheet_name: str, courier_map: Dict[str, Any]) -> Any:
    sheet_lower = sheet_name.lower()
    for name in sorted(courier_map.keys(), key=len, reverse=True):
        if name in sheet_lower:
            return courier_map[name]
    return None

def clean_mode_str(mode_str):
    if not isinstance(mode_str, str): return ""
    return mode_str.strip()

@app.post("/process-pricing")
async def process_pricing(file: UploadFile = File(...)):
    if not FOLDER_ID or not CREDENTIALS_PATH:
        raise HTTPException(status_code=500, detail="Server configuration error: Drive credentials missing.")

    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    try:
        # Save input file
        input_file_path = os.path.join(temp_dir, file.filename)
        with open(input_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        print(f"Processing input file: {input_file_path}")
        
        # Load Mapping
        mapping_df = load_sheet_mapping(MAPPING_FILE)
        
        # Parse Input
        parser = CourierSheetParser(input_file_path)
        couriers = parser.parse()
        
        if not couriers:
            raise HTTPException(status_code=400, detail="No valid courier data found in the uploaded file.")
            
        courier_map = {c.name.lower(): c for c in couriers}
        calculator = PricingCalculator(max_weight_grams=50000, step_grams=500)
        
        # Output file path
        output_filename = "Courier_Pricing_Output.xlsx"
        output_file_path = os.path.join(temp_dir, output_filename)
        
        # Generate Output
        with pd.ExcelWriter(output_file_path, engine='openpyxl') as writer:
            has_data = False
            
            if not mapping_df.empty:
                for index, row in mapping_df.iterrows():
                    sheet_name = str(row['Sheet Name'])
                    target_mode = clean_mode_str(row['Mode'])
                    
                    is_reverse = "reverse" in target_mode.lower()
                    
                    base_mode = target_mode
                    if is_reverse:
                        if "air" in target_mode.lower():
                            base_mode = "Air"
                        elif "sdd" in target_mode.lower():
                            base_mode = "SDD"
                        elif "ndd" in target_mode.lower():
                            base_mode = "NDD"
                        else:
                            base_mode = "Surface"
                    
                    courier = find_courier_for_sheet(sheet_name, courier_map)
                    mode_df = pd.DataFrame()
                    zones_processed = False
                    
                    if courier:
                        zones = [z for z in courier.zones if z.mode.lower() == base_mode.lower()]
                        if zones:
                            for zone in zones:
                                zone_df = calculator.generate_output_dataframe(zone, force_price_zero=is_reverse)
                                mode_df = pd.concat([mode_df, zone_df], ignore_index=True)
                            zones_processed = True
                    
                    if not zones_processed:
                        # Default Zones
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
                            pass 
            else:
                # Default logic if no mapping
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
                            clean_name = "".join([c for c in sheet_name if c.isalnum() or c in ['_', ' ']])
                            mode_df.to_excel(writer, sheet_name=clean_name, index=False)
                            has_data = True
            
            if not has_data:
                raise HTTPException(status_code=400, detail="Could not generate any pricing data. Check input format.")

        # Upload to Drive
        print("Uploading to Drive...")
        input_name_stem = os.path.splitext(file.filename)[0]
        
        try:
            target_folder_id = get_or_create_folder(CREDENTIALS_PATH, FOLDER_ID, input_name_stem)
            
            input_link = upload_with_versioning(input_file_path, CREDENTIALS_PATH, target_folder_id)
            output_link = upload_with_versioning(output_file_path, CREDENTIALS_PATH, target_folder_id)
            
            return JSONResponse(content={
                "status": "success",
                "input_file_link": input_link,
                "output_file_link": output_link,
                "folder_id": target_folder_id
            })
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Drive Upload Error: {str(e)}")

    finally:
        # Cleanup
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
