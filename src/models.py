from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class SlabRule:
    weight_spec: str
    price: float
    is_incremental: bool = False
    weight_grams: int = 0
    rule_type: str = "BASE" # BASE, INCREMENTAL, RESET

@dataclass
class ZonePricing:
    zone_name: str
    mode: str
    
    # FWD Rules (Ordered)
    fwd_rules: List[SlabRule] = field(default_factory=list)
    
    # RTO Rules
    rto_rules: List[SlabRule] = field(default_factory=list)
    rto_fwd_multiplier: Optional[float] = None
    
    # RVP Rules
    rvp_rules: List[SlabRule] = field(default_factory=list)
    rvp_without_qc_price: Optional[float] = None # For flat/base
    rvp_flat_addition: Optional[float] = None
    rvp_fwd_multiplier: Optional[float] = None
    rvp_operator: str = "MAX" # Min/Max
    
    # Global/Zone Params
    qc_charges: Optional[float] = None
    cod_invoice_pct: Optional[float] = None
    cod_operator: Optional[str] = None
    cod_fixed_charge: Optional[float] = None
    volumetric_coefficient: Optional[float] = None
    tax_pct: Optional[float] = None
    is_gst_inclusive: Optional[bool] = None
    fuel_surcharge_pct: Optional[float] = None
    docket_charge: Optional[float] = None

@dataclass
class CourierData:
    name: str
    zones: List[ZonePricing] = field(default_factory=list)

