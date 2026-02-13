import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
from src.models import CourierData, ZonePricing, SlabRule
from src.utils import parse_weight_to_grams, is_incremental

class CourierSheetParser:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.courier_data = []

    def parse(self) -> List[CourierData]:
        xl = pd.ExcelFile(self.file_path)
        couriers = []
        
        for sheet_name in xl.sheet_names:
            if sheet_name == "Expected Output":
                continue
                
            df = pd.read_excel(self.file_path, sheet_name=sheet_name, header=0)
            
            # Basic cleanup
            df = df.dropna(how='all') # Drop empty rows
            
            if 'Mode' not in df.columns or 'Zone' not in df.columns:
                print(f"Skipping sheet {sheet_name}: Missing 'Mode' or 'Zone' columns.")
                continue

            courier = CourierData(name=sheet_name)
    
            current_mode = None
            current_zone = None
            current_rows = []
            
            for index, row in df.iterrows():
                mode = row['Mode']
                zone = row['Zone']
                
                if pd.isna(mode) or pd.isna(zone):
                    continue
                
                if mode != current_mode or zone != current_zone:
                    if current_rows:
                        zone_pricing = self._process_zone_block(current_mode, current_zone, current_rows)
                        courier.zones.append(zone_pricing)
                    
                    current_mode = mode
                    current_zone = zone
                    current_rows = []
                
                current_rows.append(row)
            
            # Process last block
            if current_rows:
                zone_pricing = self._process_zone_block(current_mode, current_zone, current_rows)
                courier.zones.append(zone_pricing)
                
            # Post-process to fill missing globals
            self._fill_missing_globals(courier)
            
            couriers.append(courier)
            
        return couriers

    def _process_zone_block(self, mode: str, zone: str, rows: List[pd.Series]) -> ZonePricing:
        zp = ZonePricing(zone_name=zone, mode=mode)
        
        # Parse global params from the first row of the block
        first_row = rows[0]
        
        # Helper to safely get float
        def get_float(row, col_name):
            val = row.get(col_name)
            if pd.isna(val):
                return None
            try:
                return float(val)
            except:
                return None

        def get_str(row, col_name):
            val = row.get(col_name)
            if pd.isna(val):
                return None
            return str(val).strip()
            
        def get_bool(row, col_name):
            val = row.get(col_name)
            if pd.isna(val):
                return None
            if isinstance(val, bool):
                return val
            val_str = str(val).lower().strip()
            if val_str in ['true', '1.0','1' 'yes']:
                return True
            if val_str in ['false', '0.0', '0' 'no']:
                return False
            return None

        zp.qc_charges = get_float(first_row, 'QC Charges(Rs)')
        zp.cod_invoice_pct = get_float(first_row, 'Invoice Percentage for COD(Optional)%')
        zp.cod_operator = get_str(first_row, 'COD Operator(Min/Max)') or "MAX"
        zp.cod_fixed_charge = get_float(first_row, 'Fixed COD Charge(Optional)')
        zp.volumetric_coefficient = get_float(first_row, 'Volumetric Coefficient') or 5000.0
        zp.tax_pct = get_float(first_row, 'Tax(%)') or 18.0
        zp.is_gst_inclusive = get_bool(first_row, 'Is GST Inclusive')
        zp.fuel_surcharge_pct = get_float(first_row, 'Fuel Surcharge(%)') or 0.0
        zp.docket_charge = get_float(first_row, 'Docket Charge') or 0.0
        
        # Parse Slabs
        for row in rows:
            # FWD
            fwd_weight = get_str(row, 'FWD Weight')
            fwd_price = get_float(row, 'FWD Price(Rs)')
            
            if fwd_weight and fwd_price is not None:
                grams = parse_weight_to_grams(fwd_weight)
                is_inc = is_incremental(fwd_weight)
                rule_type = "INCREMENTAL" if is_inc else ("BASE" if not zp.fwd_rules else "RESET")
                
                slab = SlabRule(weight_spec=fwd_weight, price=fwd_price, is_incremental=is_inc, weight_grams=grams, rule_type=rule_type)
                zp.fwd_rules.append(slab)

            # RTO
            rto_weight = get_str(row, 'RTO Weight')
            rto_price = get_float(row, 'RTO Price(Rs)')
            if rto_weight and rto_price is not None:
                grams = parse_weight_to_grams(rto_weight)
                is_inc = is_incremental(rto_weight)
                rule_type = "INCREMENTAL" if is_inc else ("BASE" if not zp.rto_rules else "RESET")
                slab = SlabRule(weight_spec=rto_weight, price=rto_price, is_incremental=is_inc, weight_grams=grams, rule_type=rule_type)
                zp.rto_rules.append(slab)
            
            # RTO Multiplier
            rto_mult = get_float(row, 'FWD multiplier for RTO')
            if rto_mult is not None and pd.isna(zp.rto_fwd_multiplier):
                 zp.rto_fwd_multiplier = rto_mult

            # RVP
            rvp_weight = get_str(row, 'RVP Weight')
            rvp_price = get_float(row, 'RVP Without QC Price(Rs)')
            if rvp_weight and rvp_price is not None:
                grams = parse_weight_to_grams(rvp_weight)
                is_inc = is_incremental(rvp_weight)
                rule_type = "INCREMENTAL" if is_inc else ("BASE" if not zp.rvp_rules else "RESET")
                slab = SlabRule(weight_spec=rvp_weight, price=rvp_price, is_incremental=is_inc, weight_grams=grams, rule_type=rule_type)
                zp.rvp_rules.append(slab)
            
            # RVP Flat/Multiplier
            rvp_flat = get_float(row, 'Additional flat charges over FWD for RVP Without QC(Rs)')
            if rvp_flat is not None and pd.isna(zp.rvp_flat_addition):
                zp.rvp_flat_addition = rvp_flat
                
            rvp_mult = get_float(row, 'FWD multiplier for RVP')
            if rvp_mult is not None and pd.isna(zp.rvp_fwd_multiplier):
                zp.rvp_fwd_multiplier = rvp_mult
                
            rvp_op = get_str(row, 'RVP Operator(Min/Max)')
            if rvp_op:
                zp.rvp_operator = rvp_op

        return zp

    def _fill_missing_globals(self, courier: CourierData):
        # Fields to check:
        fields = [
            'qc_charges', 'cod_invoice_pct', 'cod_operator', 'cod_fixed_charge',
            'volumetric_coefficient', 'tax_pct', 'is_gst_inclusive',
            'fuel_surcharge_pct', 'docket_charge'
        ]
        
        # Default values (if missing everywhere)
        defaults = {
            'cod_operator': 'MAX',
            'volumetric_coefficient': 5000.0,
            'tax_pct': 18.0,
            'is_gst_inclusive': False,
            'fuel_surcharge_pct': 0.0,
            'docket_charge': 0.0,
            'qc_charges': 0.0,
            'cod_invoice_pct': 1.5,
            'cod_fixed_charge': 30.0
        }
        
        found_values = {}
        for field_name in fields:
            for zone in courier.zones:
                val = getattr(zone, field_name)
                if val is not None:
                    found_values[field_name] = val
                    break # Found one, use it as source of truth
        
        # Apply to all zones that are "missing" (None)
        for field_name in fields:
            ref_val = found_values.get(field_name, defaults.get(field_name))
            
            for zone in courier.zones:
                current_val = getattr(zone, field_name)
                if current_val is None:
                    print(f"Auto-filling {field_name} for {zone.zone_name} with {ref_val}")
                    setattr(zone, field_name, ref_val)
