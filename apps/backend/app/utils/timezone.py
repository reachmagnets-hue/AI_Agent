import re
from datetime import datetime, timezone, timedelta
import structlog

logger = structlog.get_logger(__name__)

# Basic US Area Code to UTC Offset mapping (Standard Time)
# Eastern: -5, Central: -6, Mountain: -7, Pacific: -8
AREA_CODE_OFFSETS = {
    # Eastern (UTC-5)
    "201": -5, "207": -5, "212": -5, "215": -5, "229": -5, "234": -5, "239": -5, "240": -5,
    "267": -5, "272": -5, "302": -5, "305": -5, "315": -5, "321": -5, "330": -5, "339": -5,
    "347": -5, "351": -5, "352": -5, "386": -5, "401": -5, "404": -5, "407": -5, "412": -5,
    "413": -5, "443": -5, "470": -5, "475": -5, "478": -5, "484": -5, "508": -5, "513": -5,
    "516": -5, "518": -5, "540": -5, "561": -5, "570": -5, "585": -5, "607": -5, "609": -5,
    "617": -5, "631": -5, "646": -5, "678": -5, "704": -5, "706": -5, "716": -5, "718": -5,
    "724": -5, "732": -5, "754": -5, "757": -5, "770": -5, "772": -5, "781": -5, "786": -5,
    "803": -5, "804": -5, "813": -5, "814": -5, "828": -5, "845": -5, "848": -5, "854": -5,
    "856": -5, "857": -5, "860": -5, "862": -5, "864": -5, "904": -5, "908": -5, "910": -5,
    "914": -5, "917": -5, "919": -5, "929": -5, "937": -5, "941": -5, "954": -5, "973": -5,
    "978": -5, "980": -5, "984": -5,

    # Central (UTC-6)
    "205": -6, "214": -6, "217": -6, "218": -6, "224": -6, "225": -6, "228": -6, "251": -6,
    "254": -6, "256": -6, "262": -6, "270": -6, "309": -6, "312": -6, "314": -6, "318": -6,
    "319": -6, "325": -6, "331": -6, "334": -6, "361": -6, "405": -6, "409": -6, "414": -6,
    "417": -6, "469": -6, "479": -6, "504": -6, "507": -6, "512": -6, "515": -6, "573": -6,
    "601": -6, "605": -6, "612": -6, "615": -6, "618": -6, "630": -6, "636": -6, "641": -6,
    "662": -6, "682": -6, "701": -6, "708": -6, "712": -6, "713": -6, "715": -6, "731": -6,
    "769": -6, "773": -6, "779": -6, "785": -6, "812": -6, "815": -6, "816": -6, "817": -6,
    "830": -6, "832": -6, "847": -6, "865": -6, "901": -6, "903": -6, "913": -6, "915": -6,
    "918": -6, "920": -6, "931": -6, "936": -6, "940": -6, "952": -6, "956": -6, "972": -6,
    "979": -6, "985": -6,

    # Mountain (UTC-7)
    "208": -7, "303": -7, "307": -7, "406": -7, "435": -7, "480": -7, "505": -7, "520": -7,
    "575": -7, "602": -7, "623": -7, "720": -7, "801": -7, "928": -7, "970": -7,

    # Pacific (UTC-8)
    "206": -8, "209": -8, "213": -8, "253": -8, "310": -8, "323": -8, "360": -8, "408": -8,
    "415": -8, "424": -8, "425": -8, "442": -8, "503": -8, "509": -8, "510": -8, "530": -8,
    "541": -8, "559": -8, "562": -8, "619": -8, "626": -8, "650": -8, "657": -8, "661": -8,
    "702": -8, "707": -8, "714": -8, "725": -8, "747": -8, "760": -8, "805": -8, "818": -8,
    "831": -8, "858": -8, "909": -8, "916": -8, "925": -8, "949": -8, "951": -8, "971": -8
}

def get_utc_offset_for_phone(phone_number: str) -> int:
    """Extracts US area code and returns standard timezone UTC offset. Default: Eastern (-5)"""
    # Remove non-digit characters
    digits = ''.join(filter(str.isdigit, phone_number))
    
    # Standard US number format: 1XXXXXXXXXX or XXXXXXXXXX
    if len(digits) == 11 and digits.startswith("1"):
        area_code = digits[1:4]
    elif len(digits) == 10:
        area_code = digits[0:3]
    else:
        # Fallback to Eastern timezone
        return -5
        
    return AREA_CODE_OFFSETS.get(area_code, -5)

# Mapping of US State Codes to standard time UTC offsets
STATE_TZ_OFFSETS = {
    "AL": -6, "AR": -6, "AS": -11, "AZ": -7, "CA": -8, "CO": -7, "CT": -5, "DE": -5, "DC": -5, "FL": -5, "GA": -5,
    "GU": 10, "HI": -10, "ID": -7, "IL": -6, "IN": -5, "IA": -6, "KS": -6, "KY": -5, "LA": -6, "ME": -5, "MD": -5,
    "MA": -5, "MI": -5, "MN": -6, "MS": -6, "MO": -6, "MT": -7, "NE": -6, "NV": -8, "NH": -5, "NJ": -5, "NM": -7,
    "NY": -5, "NC": -5, "ND": -6, "MP": 10, "OH": -5, "OK": -6, "OR": -8, "PA": -5, "PR": -4, "RI": -5, "SC": -5,
    "SD": -6, "TN": -6, "TX": -6, "UT": -7, "VT": -5, "VA": -5, "VI": -4, "WA": -8, "WV": -5, "WI": -6, "WY": -7
}

def is_within_calling_hours(phone_number: str, state_code: str = None) -> bool:
    """
    Checks if current time in prospect's local timezone is between 8:00 AM and 9:00 PM.
    Uses state_code offset mapping if provided, else falls back to US Area Code parsing.
    Bypassed in development environment.
    """
    from app.core.config import get_settings
    settings = get_settings()
    if settings.ENVIRONMENT == "development":
        logger.info("Bypassing timezone compliance check in development environment", phone_number=phone_number)
        return True
        
    offset = None
    if state_code:
        clean_state = state_code.strip().upper()
        offset = STATE_TZ_OFFSETS.get(clean_state)
        
    if offset is None:
        offset = get_utc_offset_for_phone(phone_number)
        
    # Calculate time in target timezone
    target_tz = timezone(timedelta(hours=offset))
    now_target = datetime.now(timezone.utc).astimezone(target_tz)
    
    current_hour = now_target.hour
    
    # Allow calling between 8 AM (8:00) and 9 PM (21:00)
    is_valid = 8 <= current_hour < 21
    
    logger.info(
        "Timezone compliance check",
        phone_number=phone_number,
        state_code=state_code,
        target_local_time=now_target.strftime("%Y-%m-%d %H:%M:%S %Z"),
        current_hour=current_hour,
        is_valid=is_valid
    )
    
    return is_valid
