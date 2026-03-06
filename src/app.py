import os
import json
import shutil
import tempfile
import traceback
import pandas as pd
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from src.parser import CourierSheetParser
from src.logic import PricingCalculator
from src.drive_uploader import (
    get_or_create_folder, upload_with_versioning,
    extract_file_id_from_link, check_drive_access, download_drive_file,
    get_service_account_email
)
from src.models import ZonePricing
from src.validator import validate_courier_data
from src.logger import get_logger

logger = get_logger(__name__)

load_dotenv()
FOLDER_ID = os.getenv("FOLDER_ID")
CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH")
MAPPING_FILE = os.getenv("MAPPING_FILE_PATH", "Courier_ids_Modes.xlsx")
GOOGLE_CLIENT_ID = os.getenv("VITE_GOOGLE_CLIENT_ID", "")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
BASE_PATH = os.getenv("BASE_PATH")

logger.info("Starting Courier Pricing Automation API v2")
logger.info("FOLDER_ID=%s, CREDENTIALS_PATH=%s, MAPPING_FILE=%s", FOLDER_ID, CREDENTIALS_PATH, MAPPING_FILE)

app = FastAPI(title="Courier Pricing Automation API", root_path=BASE_PATH if BASE_PATH != "/" else "")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": str(exc)})

# --- Data Persistence (JSON files in data/) ---

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def get_couriers_file():
    return os.path.join(DATA_DIR, "couriers.json")

def get_mapping_file():
    return os.path.join(DATA_DIR, "courier_modes_mapping.json")

def get_defaults_file():
    return os.path.join(DATA_DIR, "defaults.json")

def load_json(path, default=None):
    if default is None:
        default = []
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default

def save_json(path, data):
    ensure_data_dir()
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    logger.debug("Saved JSON to %s", path)

def init_data_from_excel():
    """Initialize data files from Courier_ids_Modes.xlsx if they don't exist."""
    ensure_data_dir()
    mapping_json_path = get_mapping_file()
    couriers_json_path = get_couriers_file()
    defaults_json_path = get_defaults_file()

    if not os.path.exists(mapping_json_path) and os.path.exists(MAPPING_FILE):
        try:
            df = pd.read_excel(MAPPING_FILE)
            records = df.to_dict(orient="records")
            save_json(mapping_json_path, records)
            logger.info("Initialized mapping JSON from %s (%d records)", MAPPING_FILE, len(records))
        except Exception as e:
            logger.error("Error initializing mapping from Excel: %s", e, exc_info=True)

    if not os.path.exists(couriers_json_path):
        mapping = load_json(get_mapping_file())
        courier_names = set()
        for rec in mapping:
            sn = rec.get("Sheet Name", "")
            parts = sn.split("_")
            if parts:
                courier_names.add(parts[0])
        couriers = sorted(list(courier_names))
        save_json(couriers_json_path, couriers)
        logger.info("Initialized couriers JSON with %d couriers", len(couriers))

    if not os.path.exists(defaults_json_path):
        defaults = {
            "volumetric_coefficient": 5000.0,
            "tax_pct": 18.0,
            "is_gst_inclusive": False,
            "fuel_surcharge_pct": 0.0,
            "docket_charge": 0.0,
            "qc_charges": 0.0,
            "cod_invoice_pct": 1.5,
            "cod_operator": "MAX",
            "cod_fixed_charge": 30.0
        }
        save_json(defaults_json_path, defaults)
        logger.info("Initialized defaults JSON")

init_data_from_excel()

# --- Pydantic Models ---

class DefaultsModel(BaseModel):
    volumetric_coefficient: float = 5000.0
    tax_pct: float = 18.0
    is_gst_inclusive: bool = False
    fuel_surcharge_pct: float = 0.0
    docket_charge: float = 0.0
    qc_charges: float = 0.0
    cod_invoice_pct: float = 1.5
    cod_operator: str = "MAX"
    cod_fixed_charge: float = 30.0

class MappingRecord(BaseModel):
    sheet_name: str
    mode: str

# --- API Endpoints ---

@app.get("/api/config")
async def get_config():
    sa_email = ""
    if CREDENTIALS_PATH and os.path.exists(CREDENTIALS_PATH):
        sa_email = get_service_account_email(CREDENTIALS_PATH)
    return {"googleClientId": GOOGLE_CLIENT_ID, "serviceAccountEmail": sa_email}

@app.get("/api/me")
async def get_me(request: Request):
    """Validate token and return user info."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth.split(" ", 1)[1]
    try:
        import base64
        payload = json.loads(base64.b64decode(token.split(".")[1] + "=="))
        email = payload.get("email", "")
        if not email.endswith("@prozo.com"):
            logger.warning("Access denied for non-prozo email: %s", email)
            raise HTTPException(status_code=403, detail="Access denied")
        logger.info("User authenticated: %s", email)
        return {"email": email, "name": payload.get("name", ""), "role": "admin"}
    except HTTPException:
        raise
    except Exception:
        logger.warning("Invalid token received", exc_info=True)
        raise HTTPException(status_code=401, detail="Invalid token")

# --- Settings: Couriers ---

@app.get("/api/couriers")
async def get_couriers():
    return load_json(get_couriers_file(), [])

@app.post("/api/couriers")
async def save_couriers(request: Request):
    data = await request.json()
    save_json(get_couriers_file(), data)
    logger.info("Couriers list updated (%d entries)", len(data) if isinstance(data, list) else 0)
    return {"status": "ok"}

# --- Settings: Courier Modes Mapping ---

@app.get("/api/mapping")
async def get_mapping():
    return load_json(get_mapping_file(), [])

@app.post("/api/mapping")
async def save_mapping(request: Request):
    data = await request.json()
    save_json(get_mapping_file(), data)
    logger.info("Courier modes mapping updated (%d entries)", len(data) if isinstance(data, list) else 0)
    return {"status": "ok"}

# --- Settings: Defaults ---

@app.get("/api/defaults")
async def get_defaults():
    return load_json(get_defaults_file(), {})

@app.post("/api/defaults")
async def save_defaults(request: Request):
    data = await request.json()
    save_json(get_defaults_file(), data)
    logger.info("Default values updated")
    return {"status": "ok"}

# --- Core Processing Endpoints ---

@app.post("/api/detect-sheets")
async def detect_sheets(file: UploadFile = File(...)):
    """Upload a file and return the list of sheet names found in it."""
    filename = os.path.basename(file.filename or "upload.xlsx")
    logger.info("[detect-sheets] Received file: %s", filename)
    temp_dir = tempfile.mkdtemp()
    try:
        input_file_path = os.path.join(temp_dir, filename)

        contents = await file.read()
        with open(input_file_path, "wb") as buffer:
            buffer.write(contents)
        logger.info("[detect-sheets] File saved to temp: %s (%d bytes)", input_file_path, len(contents))

        xl = pd.ExcelFile(input_file_path)
        logger.info("[detect-sheets] Excel has %d sheets: %s", len(xl.sheet_names), xl.sheet_names)

        sheets = []
        for sn in xl.sheet_names:
            if sn.lower() == "expected output":
                logger.debug("[detect-sheets] Skipping sheet: %s", sn)
                continue
            df = pd.read_excel(input_file_path, sheet_name=sn, header=0, nrows=0)
            has_mode = "Mode" in df.columns
            has_zone = "Zone" in df.columns
            valid = has_mode and has_zone
            sheets.append({
                "name": sn,
                "valid": valid,
                "error": None if valid else "Missing 'Mode' or 'Zone' columns"
            })
            logger.info("[detect-sheets] Sheet '%s': valid=%s, columns=%s", sn, valid, list(df.columns))

        logger.info("[detect-sheets] Returning %d sheets", len(sheets))
        return {"sheets": sheets}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[detect-sheets] Error: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.post("/api/detect-sheets-from-drive")
async def detect_sheets_from_drive(request: Request):
    """Accept a Drive link, check access, download, and return sheet names."""
    body = await request.json()
    drive_link = body.get("drive_link", "").strip()
    if not drive_link:
        raise HTTPException(status_code=400, detail="drive_link is required.")

    if not CREDENTIALS_PATH:
        raise HTTPException(status_code=500, detail="Server configuration error: Drive credentials missing.")

    logger.info("[detect-sheets-drive] Received link: %s", drive_link)

    try:
        file_id = extract_file_id_from_link(drive_link)
        logger.info("[detect-sheets-drive] Extracted file ID: %s", file_id)
    except ValueError as e:
        logger.warning("[detect-sheets-drive] Invalid link: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

    access = check_drive_access(file_id, CREDENTIALS_PATH)
    if not access["accessible"]:
        sa_email = get_service_account_email(CREDENTIALS_PATH)
        logger.warning("[detect-sheets-drive] Access denied for file %s", file_id)
        return JSONResponse(status_code=200, content={
            "status": "access_denied",
            "message": access["error"],
            "service_account_email": sa_email
        })

    temp_dir = tempfile.mkdtemp()
    try:
        local_path = download_drive_file(file_id, CREDENTIALS_PATH, temp_dir)
        logger.info("[detect-sheets-drive] Downloaded to: %s", local_path)

        xl = pd.ExcelFile(local_path)
        logger.info("[detect-sheets-drive] Excel has %d sheets: %s", len(xl.sheet_names), xl.sheet_names)

        sheets = []
        for sn in xl.sheet_names:
            if sn.lower() == "expected output":
                continue
            df = pd.read_excel(local_path, sheet_name=sn, header=0, nrows=0)
            has_mode = "Mode" in df.columns
            has_zone = "Zone" in df.columns
            valid = has_mode and has_zone
            sheets.append({
                "name": sn,
                "valid": valid,
                "error": None if valid else "Missing 'Mode' or 'Zone' columns"
            })

        logger.info("[detect-sheets-drive] Returning %d sheets, drive_file_id=%s, file_name=%s",
                     len(sheets), file_id, access["file_name"])
        return {
            "status": "ok",
            "sheets": sheets,
            "drive_file_id": file_id,
            "file_name": access["file_name"]
        }
    except Exception as e:
        logger.error("[detect-sheets-drive] Error: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.post("/api/process")
async def process_pricing(
    file: UploadFile = File(None),
    merchant_name: str = Form(...),
    sheet_courier_mapping: str = Form(...),
    force: str = Form("false"),
    drive_link: str = Form("")
):
    """
    Process the uploaded file (or Drive link) with explicit sheet-to-courier mapping.
    sheet_courier_mapping is a JSON string: { "SheetName": ["Courier1", "Courier2"], ... }
    force: "true" to skip warnings (zones without FWD rules).
    drive_link: optional Google Drive link; if provided, file upload is not required.
    """
    has_file = file is not None and file.filename
    has_drive_link = bool(drive_link.strip())

    logger.info("[process] Started for merchant='%s', force=%s, file='%s', drive_link='%s'",
                merchant_name, force, file.filename if has_file else "(none)", drive_link[:60] if has_drive_link else "(none)")

    if not has_file and not has_drive_link:
        raise HTTPException(status_code=400, detail="Either a file upload or a drive_link is required.")

    if not FOLDER_ID or not CREDENTIALS_PATH:
        logger.error("[process] Drive credentials missing: FOLDER_ID=%s, CREDENTIALS_PATH=%s", FOLDER_ID, CREDENTIALS_PATH)
        raise HTTPException(status_code=500, detail="Server configuration error: Drive credentials missing.")

    try:
        mapping_dict = json.loads(sheet_courier_mapping)
        logger.info("[process] Sheet-courier mapping: %s", mapping_dict)
    except json.JSONDecodeError:
        logger.error("[process] Invalid sheet_courier_mapping JSON: %s", sheet_courier_mapping)
        raise HTTPException(status_code=400, detail="Invalid sheet_courier_mapping JSON.")

    courier_modes_mapping = load_json(get_mapping_file(), [])
    logger.info("[process] Loaded %d courier mode mapping records", len(courier_modes_mapping))

    defaults = load_json(get_defaults_file(), {})

    temp_dir = tempfile.mkdtemp()
    try:
        # Resolve input file: from upload or Drive download
        if has_drive_link:
            try:
                file_id = extract_file_id_from_link(drive_link.strip())
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            logger.info("[process] Downloading from Drive: file_id=%s", file_id)
            downloaded_path = download_drive_file(file_id, CREDENTIALS_PATH, temp_dir)
            original_ext = os.path.splitext(downloaded_path)[1] or ".xlsx"
            input_filename = f"{merchant_name.strip()}_base_file{original_ext}"
            input_file_path = os.path.join(temp_dir, input_filename)
            if downloaded_path != input_file_path:
                shutil.copy2(downloaded_path, input_file_path)
            logger.info("[process] Drive file ready: %s", input_filename)
        else:
            original_ext = os.path.splitext(file.filename or "upload.xlsx")[1] or ".xlsx"
            input_filename = f"{merchant_name.strip()}_base_file{original_ext}"
            input_file_path = os.path.join(temp_dir, input_filename)
            contents = await file.read()
            with open(input_file_path, "wb") as buffer:
                buffer.write(contents)
            logger.info("[process] Saved uploaded file: %s (%d bytes)", input_filename, len(contents))

        # Parse
        logger.info("[process] Parsing input file...")
        parser = CourierSheetParser(input_file_path)
        all_couriers = parser.parse()

        if not all_couriers:
            logger.warning("[process] No valid courier data found in uploaded file")
            raise HTTPException(status_code=400, detail="No valid courier data found in the uploaded file.")

        logger.info("[process] Parsed %d courier(s): %s", len(all_couriers), [c.name for c in all_couriers])

        sheet_data_map = {c.name: c for c in all_couriers}

        # Build courier mapping
        courier_to_data = {}
        for sheet_name, courier_names in mapping_dict.items():
            if sheet_name not in sheet_data_map:
                logger.error("[process] Sheet '%s' not found in uploaded file. Available: %s", sheet_name, list(sheet_data_map.keys()))
                raise HTTPException(status_code=400, detail=f"Sheet '{sheet_name}' not found in uploaded file.")
            for cn in courier_names:
                courier_to_data[cn.lower()] = sheet_data_map[sheet_name]
        logger.info("[process] Courier-to-data mapping: %s", list(courier_to_data.keys()))

        # Validate
        logger.info("[process] Validating courier data...")
        all_errors = []
        all_warnings = []
        for courier_name_lower, courier_data in courier_to_data.items():
            result = validate_courier_data(courier_data)
            for err in result.get("errors", []):
                all_errors.append(f"[{courier_data.name}] {err}")
            for warn in result.get("warnings", []):
                all_warnings.append(f"[{courier_data.name}] {warn}")

        if all_errors:
            logger.warning("[process] Validation errors (%d): %s", len(all_errors), all_errors)
            raise HTTPException(status_code=422, detail={
                "message": "Validation failed: Missing data in the base file. Please fix and re-upload.",
                "errors": all_errors
            })

        if all_warnings:
            logger.info("[process] Validation warnings (%d): %s", len(all_warnings), all_warnings)

        skip_warnings = force.lower() in ("true", "1", "yes")
        if all_warnings and not skip_warnings:
            logger.info("[process] Returning warnings to user for confirmation")
            return JSONResponse(status_code=200, content={
                "status": "warnings",
                "message": "Some zones have no FWD pricing rules. Do you want to continue?",
                "warnings": all_warnings
            })

        # Generate output
        logger.info("[process] Generating pricing output (max_weight=50000, step=500)...")
        calculator = PricingCalculator(max_weight_grams=50000, step_grams=500)

        output_filename = f"{merchant_name.strip()}_pricing.xlsx"
        output_file_path = os.path.join(temp_dir, output_filename)

        sheets_generated = 0
        with pd.ExcelWriter(output_file_path, engine="openpyxl") as writer:
            has_data = False

            for mapping_rec in courier_modes_mapping:
                sheet_name = mapping_rec.get("Sheet Name", "")
                target_mode = mapping_rec.get("Mode", "").strip()

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

                courier_data = None
                sheet_lower = sheet_name.lower()
                for cn, cd in courier_to_data.items():
                    if cn in sheet_lower:
                        courier_data = cd
                        break

                mode_df = pd.DataFrame()
                zones_processed = False

                if courier_data:
                    zones = [z for z in courier_data.zones if z.mode.lower() == base_mode.lower()]
                    if zones:
                        for zone in zones:
                            zone_df = calculator.generate_output_dataframe(zone, force_price_zero=is_reverse)
                            mode_df = pd.concat([mode_df, zone_df], ignore_index=True)
                        zones_processed = True
                        logger.debug("[process] Sheet '%s': matched courier, %d zones for mode '%s'", sheet_name, len(zones), base_mode)

                if not zones_processed:
                    zone_names = ["Local", "Within State", "Metro", "Rest of India", "Special Zone"]
                    for z_name in zone_names:
                        dummy_zp = create_default_zone_pricing(z_name, base_mode)
                        zone_df = calculator.generate_output_dataframe(dummy_zp, force_price_zero=False)
                        mode_df = pd.concat([mode_df, zone_df], ignore_index=True)
                    logger.debug("[process] Sheet '%s': no matching courier, using defaults", sheet_name)

                if not mode_df.empty:
                    final_sheet_name = sheet_name[:31]
                    try:
                        mode_df.to_excel(writer, sheet_name=final_sheet_name, index=False)
                        has_data = True
                        sheets_generated += 1
                    except ValueError as ve:
                        logger.warning("[process] Could not write sheet '%s': %s", final_sheet_name, ve)

            if not has_data:
                logger.error("[process] No pricing data generated")
                raise HTTPException(status_code=400, detail="Could not generate any pricing data.")

        logger.info("[process] Output file generated: %s (%d sheets)", output_filename, sheets_generated)

        # Upload to Drive
        logger.info("[process] Uploading files to Google Drive (folder='%s')...", merchant_name)
        try:
            target_folder_id = get_or_create_folder(CREDENTIALS_PATH, FOLDER_ID, merchant_name)
            logger.info("[process] Drive folder ready: %s", target_folder_id)

            input_link = upload_with_versioning(input_file_path, CREDENTIALS_PATH, target_folder_id)
            logger.info("[process] Input file uploaded: %s", input_link)

            output_link = upload_with_versioning(output_file_path, CREDENTIALS_PATH, target_folder_id)
            logger.info("[process] Output file uploaded: %s", output_link)

            logger.info("[process] SUCCESS for merchant='%s'", merchant_name)
            return JSONResponse(content={
                "status": "success",
                "merchant_name": merchant_name,
                "input_file_link": input_link,
                "output_file_link": output_link,
                "folder_id": target_folder_id
            })
        except Exception as e:
            logger.error("[process] Drive upload error: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Drive Upload Error: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[process] Unexpected error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.debug("[process] Temp directory cleaned up")

def create_default_zone_pricing(zone_name: str, mode: str) -> ZonePricing:
    zp = ZonePricing(zone_name=zone_name, mode=mode)
    zp.volumetric_coefficient = 5000.0
    zp.tax_pct = 18.0
    return zp


# Serve built React app (frontend/dist) from root if present
try:
    DIST_DIR = (Path(__file__).resolve().parents[1] / "frontend" / "dist")
    logger.info("DIST_DIR", DIST_DIR)
    if DIST_DIR.exists():
        mount_path = BASE_PATH if BASE_PATH.startswith("/") else f"/{BASE_PATH}"
        if not mount_path.endswith("/"):
            mount_path = mount_path
        app.mount(mount_path, StaticFiles(directory=DIST_DIR.as_posix(), html=True), name="frontend")
except Exception:
    pass

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8001)


