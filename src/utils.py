import re

def parse_weight_to_grams(weight_str: str) -> int:
    """
    Parses strings like '0.5kg', '500g', '2 kg', 'add 0.5kg' to grams.
    Returns integer grams.
    """
    if not isinstance(weight_str, str):
        return 0
    
    clean_str = weight_str.lower().replace("add", "").strip()
    
    # Extract number and unit
    match = re.match(r"([\d\.]+)\s*([a-z]+)", clean_str)
    if not match:
        match_num = re.match(r"([\d\.]+)", clean_str)
        if match_num:
            val = float(match_num.group(1))
            if 'kg' in clean_str:
                return int(val * 1000)
            if 'gm' or 'g' in clean_str:
                return int(val)
            
            return int(val)
        return 0

    val = float(match.group(1))
    unit = match.group(2)
    
    if unit.startswith("kg"):
        return int(val * 1000)
    elif unit.startswith("g"):
        return int(val)
    
    return int(val)

def is_incremental(weight_str: str) -> bool:
    return "add" in weight_str.lower()
