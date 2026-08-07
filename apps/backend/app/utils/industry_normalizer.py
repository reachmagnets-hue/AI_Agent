def normalize_industry_name(name: str) -> str:
    """
    Normalizes industry keywords into unified canonical folder names.
    For example: 'Auto Body', 'Auto Body Care', 'AUTO BODY SHOPS', 'auto bdy sop' -> 'Auto Body Shop'
    """
    if not name or not name.strip():
        return "General Business"
    
    s = name.strip().lower()
    
    # Auto Body variations
    if any(k in s for k in ["body", "bdy"]):
        return "Auto Body Shop"
        
    # Auto Repair & Mechanic variations
    if any(k in s for k in ["mechanic", "auto repair", "car repair", "garage"]):
        return "Auto Repair & Mechanic"
        
    # Detailing variations
    if any(k in s for k in ["detail", "car wash"]):
        return "Car Detailing"
        
    # Tire variations
    if "tire" in s:
        return "Tire Shop"
        
    # Roofing variations
    if "roof" in s:
        return "Roofing"
        
    # Dental / Dentist variations
    if any(k in s for k in ["dentist", "dental"]):
        return "Dentist & Dental"
        
    # HVAC variations
    if any(k in s for k in ["hvac", "heating", "air conditioning", "cooling"]):
        return "HVAC"
        
    return name.strip().title()
