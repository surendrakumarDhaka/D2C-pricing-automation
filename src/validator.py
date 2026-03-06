from typing import List, Dict
from src.models import CourierData
from src.logger import get_logger

logger = get_logger(__name__)

REQUIRED_GLOBAL_FIELDS = [
    ("volumetric_coefficient", "Volumetric Coefficient"),
    ("tax_pct", "Tax(%)"),
    ("fuel_surcharge_pct", "Fuel Surcharge(%)"),
    ("docket_charge", "Docket Charge"),
]

REQUIRED_COD_FIELDS = [
    ("cod_invoice_pct", "Invoice Percentage for COD(Optional)%"),
    ("cod_operator", "COD Operator(Min/Max)"),
    ("cod_fixed_charge", "Fixed COD Charge(Optional)"),
]

def validate_courier_data(courier: CourierData) -> Dict[str, List[str]]:
    """
    Validates parsed courier data.
    Returns dict with:
      - "errors": hard-stop issues (zone HAS FWD rules but is missing other details) - aggregated by mode
      - "warnings": zones that have NO FWD rules at all (may be intentionally empty) - aggregated by mode
    """
    logger.info("Validating courier: '%s' (%d zones)", courier.name, len(courier.zones))
    errors = []
    warnings = []

    if not courier.zones:
        errors.append("No zones/modes found.")
        logger.warning("Courier '%s': no zones found", courier.name)
        return {"errors": errors, "warnings": warnings}

    # Group zones by mode for aggregation
    from collections import defaultdict
    mode_warnings = defaultdict(list)  # mode -> list of zone names without FWD rules
    mode_errors = defaultdict(lambda: defaultdict(list))  # mode -> field_name -> list of zone names
    
    for zone in courier.zones:
        mode = zone.mode.strip()
        zone_name = zone.zone_name.strip()

        if not zone.fwd_rules:
            mode_warnings[mode].append(zone_name)
            logger.warning("Courier '%s', Mode='%s', Zone='%s': no FWD pricing rules (warning)", 
                         courier.name, mode, zone_name)
            continue

        # Check required global fields
        for field_name, display_name in REQUIRED_GLOBAL_FIELDS:
            val = getattr(zone, field_name, None)
            if val is None:
                mode_errors[mode][display_name].append(zone_name)
                logger.warning("Courier '%s', Mode='%s', Zone='%s': missing '%s'", 
                             courier.name, mode, zone_name, display_name)

        # Check RTO data
        if not zone.rto_rules and zone.rto_fwd_multiplier is None:
            mode_errors[mode]["RTO data (no slabs and no FWD multiplier)"].append(zone_name)
            logger.warning("Courier '%s', Mode='%s', Zone='%s': missing RTO data", 
                         courier.name, mode, zone_name)

        # Check RVP data
        has_rvp_slabs = bool(zone.rvp_rules)
        has_rvp_formula = (zone.rvp_flat_addition is not None or zone.rvp_fwd_multiplier is not None)
        if not has_rvp_slabs and not has_rvp_formula:
            mode_errors[mode]["RVP data (no slabs, no flat addition, no multiplier)"].append(zone_name)
            logger.warning("Courier '%s', Mode='%s', Zone='%s': missing RVP data", 
                         courier.name, mode, zone_name)

    # Aggregate warnings by mode
    for mode, zone_list in mode_warnings.items():
        if len(zone_list) == 1:
            warnings.append(f"Mode '{mode}': Zone '{zone_list[0]}' has no FWD pricing rules.")
        else:
            zones_str = ", ".join(f"'{z}'" for z in zone_list)
            warnings.append(f"Mode '{mode}': Zones ({zones_str}) have no FWD pricing rules.")

    # Aggregate errors by mode
    for mode, field_dict in mode_errors.items():
        error_parts = []
        for field_name, zone_list in field_dict.items():
            if len(zone_list) == 1:
                error_parts.append(f"Zone '{zone_list[0]}' missing '{field_name}'")
            else:
                zones_str = ", ".join(f"'{z}'" for z in zone_list)
                error_parts.append(f"Zones ({zones_str}) missing '{field_name}'")
        
        if error_parts:
            errors.append(f"Mode '{mode}': {'; '.join(error_parts)}.")

    logger.info("Courier '%s' validation complete: %d error(s), %d warning(s)", courier.name, len(errors), len(warnings))
    return {"errors": errors, "warnings": warnings}
