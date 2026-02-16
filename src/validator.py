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
      - "errors": hard-stop issues (zone HAS FWD rules but is missing other details)
      - "warnings": zones that have NO FWD rules at all (may be intentionally empty)
    """
    logger.info("Validating courier: '%s' (%d zones)", courier.name, len(courier.zones))
    errors = []
    warnings = []

    if not courier.zones:
        errors.append("No zones/modes found.")
        logger.warning("Courier '%s': no zones found", courier.name)
        return {"errors": errors, "warnings": warnings}

    for zone in courier.zones:
        prefix = f"Mode={zone.mode}, Zone={zone.zone_name}"

        if not zone.fwd_rules:
            warnings.append(f"{prefix}: No FWD pricing rules found.")
            logger.warning("Courier '%s', %s: no FWD pricing rules (warning)", courier.name, prefix)
            continue

        for field_name, display_name in REQUIRED_GLOBAL_FIELDS:
            val = getattr(zone, field_name, None)
            if val is None:
                errors.append(f"{prefix}: Missing '{display_name}'.")
                logger.warning("Courier '%s', %s: missing '%s'", courier.name, prefix, display_name)

        if not zone.rto_rules and zone.rto_fwd_multiplier is None:
            errors.append(f"{prefix}: Missing RTO data (no slabs and no FWD multiplier).")
            logger.warning("Courier '%s', %s: missing RTO data", courier.name, prefix)

        has_rvp_slabs = bool(zone.rvp_rules)
        has_rvp_formula = (zone.rvp_flat_addition is not None or zone.rvp_fwd_multiplier is not None)
        if not has_rvp_slabs and not has_rvp_formula:
            errors.append(f"{prefix}: Missing RVP data (no slabs, no flat addition, no multiplier).")
            logger.warning("Courier '%s', %s: missing RVP data", courier.name, prefix)

    logger.info("Courier '%s' validation complete: %d error(s), %d warning(s)", courier.name, len(errors), len(warnings))
    return {"errors": errors, "warnings": warnings}
