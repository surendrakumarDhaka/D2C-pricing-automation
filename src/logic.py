import math
import pandas as pd
from typing import List, Dict, Any, Optional
from src.models import ZonePricing, SlabRule

class PriceEngine:
    def __init__(self, rules: List[SlabRule]):
        self.rules = rules
        self.checkpoints = {} # weight -> price
        self.rates = [] # (start_weight, step_grams, price)
        self._build_model()

    def _build_model(self):
        last_checkpoint_w = 0
        
        for rule in self.rules:
            if rule.rule_type in ["BASE", "RESET"]:
                self.checkpoints[rule.weight_grams] = rule.price
                last_checkpoint_w = rule.weight_grams
            elif rule.rule_type == "INCREMENTAL":
                self.rates.append({
                    "start_w": last_checkpoint_w,
                    "step": rule.weight_grams,
                    "price": rule.price
                })
        
        self.rates.sort(key=lambda x: x["start_w"], reverse=True)

    def calculate_price(self, weight: int) -> float:
        if weight in self.checkpoints:
            return self.checkpoints[weight]
            
        prev_checkpoints = [w for w in self.checkpoints.keys() if w < weight]
        if prev_checkpoints:
            applicable_checkpoint_w = max(prev_checkpoints)
            applicable_checkpoint_p = self.checkpoints[applicable_checkpoint_w]
        else:
            if self.checkpoints:
                first_w = min(self.checkpoints.keys())
                if weight < first_w:
                    return self.checkpoints[first_w]
            return 0.0

        rate = next((r for r in self.rates if r["start_w"] <= applicable_checkpoint_w), None)
        
        if not rate:
            return applicable_checkpoint_p
            
        remaining = weight - applicable_checkpoint_w
        if remaining <= 0:
            return applicable_checkpoint_p
            
        steps = math.ceil(remaining / rate["step"])
        
        # Check if this step block ends at a reset checkpoint
        block_end_w = applicable_checkpoint_w + (steps * rate["step"])
        if block_end_w in self.checkpoints:
             return self.checkpoints[block_end_w]

        return applicable_checkpoint_p + (steps * rate["price"])

class PricingCalculator:
    def __init__(self, max_weight_grams: int = 50000, step_grams: int = 500):
        self.max_weight_grams = max_weight_grams
        self.step_grams = step_grams

    def generate_output_dataframe(self, zone_pricing: ZonePricing, force_price_zero: bool = False) -> pd.DataFrame:
        rows = []
        
        fwd_engine = PriceEngine(zone_pricing.fwd_rules)
        rto_engine = PriceEngine(zone_pricing.rto_rules) if zone_pricing.rto_rules else None
        rvp_engine = PriceEngine(zone_pricing.rvp_rules) if zone_pricing.rvp_rules else None
        
        # Zone Mapping
        zone_map = {
            "Local": 1,
            "Within State": 2,
            "Metro": 3,
            "Rest of India": 4,
            "Special Zone": 5
        }
        zone_id = zone_map.get(zone_pricing.zone_name.strip(), zone_pricing.zone_name)

        # Safe default getters
        def get_val(val, default):
            return val if val is not None else default

        vol_coeff = get_val(zone_pricing.volumetric_coefficient, 5000.0)
        tax_pct = get_val(zone_pricing.tax_pct, 18.0)
        fuel_surcharge = get_val(zone_pricing.fuel_surcharge_pct, 0.0)
        docket = get_val(zone_pricing.docket_charge, 0.0)
        qc = get_val(zone_pricing.qc_charges, 0.0)
        cod_pct = get_val(zone_pricing.cod_invoice_pct, 1.5)
        cod_op = get_val(zone_pricing.cod_operator, "MAX")
        cod_fixed = get_val(zone_pricing.cod_fixed_charge, 30.0)
        is_gst_inc = get_val(zone_pricing.is_gst_inclusive, False)

        for start_w in range(0, self.max_weight_grams, self.step_grams):
            end_w = start_w + self.step_grams
            
            fwd_price = fwd_engine.calculate_price(end_w)

            if is_gst_inc and fwd_price:
                fwd_price = fwd_price / 1.18
            
            rto_price = 0.0
            if rto_engine:
                rto_price = rto_engine.calculate_price(end_w)
            elif zone_pricing.rto_fwd_multiplier is not None:
                rto_price = fwd_price * zone_pricing.rto_fwd_multiplier
            
            rvp_without_qc = 0.0
            if rvp_engine:
                rvp_without_qc = rvp_engine.calculate_price(end_w)
            
            if not zone_pricing.rvp_rules:
                val1 = 0.0
                val2 = 0.0
                if zone_pricing.rvp_flat_addition is not None:
                    val1 = fwd_price + zone_pricing.rvp_flat_addition
                if zone_pricing.rvp_fwd_multiplier is not None:
                    val2 = fwd_price * zone_pricing.rvp_fwd_multiplier
                
                if zone_pricing.rvp_operator == "MAX":
                    rvp_without_qc = max(val1, val2)
                else:
                    rvp_without_qc = min(val1, val2)
            
            # 4. RVP with QC
            qc_charges = zone_pricing.qc_charges
            
            # 5. RTO Forward %
            rto_pct = 0.0
            if fwd_price > 0:
                rto_pct = rto_price / fwd_price

            final_fwd_price = fwd_price
            final_rvp_without_qc = rvp_without_qc
            
            final_rvp_with_qc = final_rvp_without_qc + qc_charges if qc_charges is not None else final_rvp_without_qc
            
            if force_price_zero:
                final_fwd_price = 0.01

            row = {
                "Zone": zone_id,
                "Start Weight(gm)": start_w,
                "Min Weight(gm)": start_w,
                "Max Weight(gm)": end_w,
                "Price": round(final_fwd_price, 2),
                "Additional Unit(gm)": 0,
                "Additional Unit Rate": 0,
                "Volumetric Coefficient": vol_coeff,
                "Tax(%)": tax_pct,
                "Fuel Surcharge(%)": fuel_surcharge,
                "Docket Charge": docket,
                "Invoice Percentage for COD(Optional)%": cod_pct,
                "COD Operator(Min/Max)(Optional)": cod_op,
                "Fixed COD Charge(Optional)": cod_fixed,
                "RVP Without QC": round(final_rvp_without_qc, 2),
                "RVP With QC": round(final_rvp_with_qc, 2),
                "RTO (Forward %)": round(rto_pct, 6)
            }
            rows.append(row)
            
        return pd.DataFrame(rows)
