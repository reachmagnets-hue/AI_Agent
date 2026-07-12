from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, desc, func, case
from typing import List, Optional
from datetime import datetime, date
from uuid import UUID
import csv
import io

from app.core.database import get_db
from app.models.lead import Lead
from app.models.call import Call
from app.models.appointment import Appointment
from app.models.campaign import Campaign
from app.utils.dnc import is_on_dnc_registry

router = APIRouter(prefix="/leads", tags=["leads"])

@router.get("/")
@router.get("")
def get_leads(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    campaign_id: Optional[str] = Query(None),
    business_type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    called_from: Optional[date] = Query(None),
    called_to: Optional[date] = Query(None),
    has_meeting: Optional[bool] = Query(None),
    no_answer: Optional[bool] = Query(None),
    has_linkedin: Optional[bool] = Query(None),
    has_email: Optional[bool] = Query(None),
    has_phone: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db)
):
    """GET paginated leads with extensive filtering capabilities"""
    query = db.query(Lead).filter(Lead.is_active == True)
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Lead.full_name.ilike(search_filter),
                Lead.phone.ilike(search_filter),
                Lead.email.ilike(search_filter),
                Lead.business_name.ilike(search_filter)
            )
        )
        
    if status:
        query = query.filter(Lead.status == status)
    if campaign_id:
        if campaign_id == "unassigned":
            query = query.filter(Lead.campaign_id.is_(None))
        else:
            try:
                camp_uuid = UUID(campaign_id)
                query = query.filter(Lead.campaign_id == camp_uuid)
            except ValueError:
                pass
    if business_type:
        query = query.filter(Lead.business_type == business_type)
    if priority:
        query = query.filter(Lead.priority == priority)
        
    if date_from:
        query = query.filter(Lead.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        query = query.filter(Lead.created_at <= datetime.combine(date_to, datetime.max.time()))
        
    if called_from:
        query = query.filter(Lead.last_called_at >= datetime.combine(called_from, datetime.min.time()))
    if called_to:
        query = query.filter(Lead.last_called_at <= datetime.combine(called_to, datetime.max.time()))
        
    if has_meeting is not None:
        if has_meeting:
            query = query.filter(Lead.appointments.any())
        else:
            query = query.filter(~Lead.appointments.any())
            
    if no_answer is not None:
        if no_answer:
            query = query.filter(Lead.total_calls == 0)
        else:
            query = query.filter(Lead.total_calls > 0)

    if has_linkedin is not None:
        if has_linkedin:
            query = query.filter(Lead.linkedin_url.isnot(None))
        else:
            query = query.filter(Lead.linkedin_url.is_(None))
            
    if has_email is not None:
        if has_email:
            query = query.filter(Lead.email.isnot(None))
        else:
            query = query.filter(Lead.email.is_(None))

    if has_phone is not None:
        if has_phone:
            query = query.filter(Lead.phone.isnot(None))
        else:
            query = query.filter(Lead.phone.is_(None))

    # Eager load campaign relationship
    query = query.options(joinedload(Lead.campaign))

    # Sort
    sort_column = getattr(Lead, sort_by, Lead.created_at)
    if sort_order.lower() == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)

    total = query.count()
    pages = (total + limit - 1) // limit
    leads = query.offset((page - 1) * limit).limit(limit).all()

    # Serialize leads to plain dicts including campaign_name
    serialized_leads = []
    for lead in leads:
        lead_dict = {c.name: getattr(lead, c.name) for c in lead.__table__.columns}
        lead_dict["campaign_name"] = lead.campaign.name if lead.campaign else None
        serialized_leads.append(lead_dict)

    # Calculate status counts for stats block using single group-by query
    status_counts = db.query(Lead.status, func.count(Lead.id))\
        .filter(Lead.is_active == True, Lead.status.in_(["pending", "interested", "meeting_booked", "not_interested"]))\
        .group_by(Lead.status).all()
    counts_map = {status: count for status, count in status_counts}
    stats = {
        "total_pending": counts_map.get("pending", 0),
        "total_interested": counts_map.get("interested", 0),
        "total_booked": counts_map.get("meeting_booked", 0),
        "total_not_interested": counts_map.get("not_interested", 0),
    }

    return {
        "leads": serialized_leads,
        "total": total,
        "page": page,
        "pages": pages,
        "stats": stats
    }

@router.get("/stats/overview")
def get_leads_overview_stats(db: Session = Depends(get_db)):
    """Overview dashboard analytics counts"""
    total_leads = db.query(Lead).filter(Lead.is_active == True).count()
    
    # By status
    status_counts = db.query(Lead.status, func.count(Lead.id))\
        .filter(Lead.is_active == True)\
        .group_by(Lead.status).all()
    by_status = {s: c for s, c in status_counts}
    
    # By campaign (SQLite-compatible: no Integer cast needed)
    from sqlalchemy import case
    campaign_rows = db.query(
        Campaign.name,
        func.count(Lead.id).label("total"),
        func.sum(case((Lead.status == "meeting_booked", 1), else_=0)).label("booked")
    ).join(Lead, Lead.campaign_id == Campaign.id)\
     .filter(Lead.is_active == True)\
     .group_by(Campaign.name).all()
    
    by_campaign = [
        {"campaign_name": name, "total": total, "booked": int(booked or 0)}
        for name, total, booked in campaign_rows
    ]
    
    # Daily counts
    from datetime import timedelta
    today_start = datetime.combine(date.today(), datetime.min.time())
    week_start = today_start - timedelta(days=7)
    
    today_called = db.query(Lead).filter(Lead.is_active == True, Lead.last_called_at >= today_start).count()
    today_answered = db.query(Call).filter(Call.started_at >= today_start, Call.status == "completed").count()
    today_booked = db.query(Appointment).filter(Appointment.created_at >= today_start).count()
    
    week_called = db.query(Lead).filter(Lead.is_active == True, Lead.last_called_at >= week_start).count()
    week_answered = db.query(Call).filter(Call.started_at >= week_start, Call.status == "completed").count()
    week_booked = db.query(Appointment).filter(Appointment.created_at >= week_start).count()
    
    # Conversion rate
    conversion_rate = 0.0
    if today_called > 0:
        conversion_rate = (today_booked / today_called) * 100.0

    return {
        "total_leads": total_leads,
        "by_status": by_status,
        "by_campaign": by_campaign,
        "today": {"called": today_called, "answered": today_answered, "booked": today_booked},
        "this_week": {"called": week_called, "answered": week_answered, "booked": week_booked},
        "conversion_rate": round(conversion_rate, 2)
    }

@router.get("/sources")
def get_lead_sources(db: Session = Depends(get_db)):
    """Get list of all imported CSV filenames (sources) and their available unassigned lead counts"""
    results = db.query(
        Lead.source,
        func.count(Lead.id).label('total'),
        func.sum(case((Lead.campaign_id.is_(None), 1), else_=0)).label('unassigned')
    ).filter(
        Lead.source.isnot(None)
    ).group_by(Lead.source).all()
    
    sources = []
    for row in results:
        sources.append({
            "source": row.source,
            "total": row.total,
            "unassigned": int(row.unassigned) if row.unassigned else 0
        })
    return sources

@router.get("/{lead_id}")
def get_lead(lead_id: UUID, db: Session = Depends(get_db)):
    """Retrieve full lead profile and linked activity history"""
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.is_active == True).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    calls = db.query(Call).filter(Call.lead_id == lead_id).order_by(desc(Call.created_at)).all()
    appointments = db.query(Appointment).filter(Appointment.lead_id == lead_id).all()
    
    # Compile chronological timeline list
    timeline: List[dict] = []
    timeline.append({
        "type": "import",
        "title": f"Lead imported from source: {lead.source}",
        "time": lead.imported_at,
        "detail": f"Imported at {lead.imported_at.strftime('%Y-%m-%d %H:%M:%S')}"
    })
    
    for call in calls:
        timeline.append({
            "type": "call",
            "title": f"Call attempt #{call.attempt_number} — Duration: {call.duration_seconds}s",
            "time": call.started_at or call.created_at,
            "detail": f"Status: {call.status} | Outcome: {call.outcome or 'Pending'}",
            "call_id": call.id,
            "transcript": call.transcript,
            "ai_summary": call.ai_summary
        })
        
        if call.sms_sent:
            timeline.append({
                "type": "sms",
                "title": f"Confirmation SMS sent to {lead.phone}",
                "time": call.started_at or call.created_at,
                "detail": "SMS notification triggered automatically."
            })
        if call.email_sent:
            timeline.append({
                "type": "email",
                "title": f"Confirmation Email sent to {lead.email or 'N/A'}",
                "time": call.started_at or call.created_at,
                "detail": "HTML follow-up email triggered automatically."
            })
            
    for appt in appointments:
        timeline.append({
            "type": "appointment",
            "title": f"Discovery meeting booked: {appt.title}",
            "time": appt.created_at,
            "detail": f"Meeting scheduled for {appt.meeting_date} at {appt.meeting_time} {appt.timezone}"
        })
        
    # Sort timeline by time descending
    timeline.sort(key=lambda x: x["time"], reverse=True)

    return {
        "lead": lead,
        "calls": calls,
        "appointments": appointments,
        "timeline": timeline
    }

@router.post("/")
def create_lead(
    full_name: Optional[str] = None,
    business_name: Optional[str] = None,
    phone: str = Query(...),
    email: Optional[str] = None,
    website: Optional[str] = None,
    business_type: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    campaign_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    """Create a single lead manually"""
    # Clean phone
    digits = ''.join(filter(str.isdigit, phone))
    formatted_phone = f"+{digits}"
    
    lead = Lead(
        full_name=full_name,
        business_name=business_name,
        phone=formatted_phone,
        email=email,
        website=website,
        business_type=business_type,
        city=city,
        state=state,
        campaign_id=campaign_id,
        status="pending"
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead

@router.post("/import")
async def import_leads_csv(
    campaign_id: Optional[UUID] = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Import CSV file of leads, enforce DNC filter, deduplication, and format verification.
    
    Smart auto-detection:
    - Phone-only list (no header): all rows treated as phone numbers
    - Email-only list: imported as email-only leads (phone = null, status = email_only)
    - Mixed list: phone leads imported normally, email-only rows stored for email outreach
    - Unknown column names: auto-detects phone/email values by pattern
    """
    contents = await file.read()
    try:
        decoded = contents.decode('utf-8-sig')
    except UnicodeDecodeError:
        try:
            decoded = contents.decode('latin-1')
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Unable to decode CSV file. Please save it as UTF-8 format."
            )

    # ── Helper predicates ───────────────────────────────────────────────────
    def _is_phone_like(val: str) -> bool:
        s = val.strip()
        if not s or len(s) > 25:
            return False
        digits = ''.join(filter(str.isdigit, s))
        return 7 <= len(digits) <= 15

    def _is_email_like(val: str) -> bool:
        s = val.strip()
        if '@' not in s:
            return False
        parts = s.split('@')
        return len(parts) == 2 and '.' in parts[1] and len(parts[0]) > 0

    # ── Detect CSV format by peeking at the first row ───────────────────────
    peek_buf = io.StringIO(decoded)
    peek_reader = csv.reader(peek_buf)
    first_row = next(peek_reader, [])
    non_empty_first = [v for v in first_row if v.strip()]

    phone_only_no_header = bool(non_empty_first) and all(_is_phone_like(v) for v in non_empty_first)
    email_only_no_header = bool(non_empty_first) and all(_is_email_like(v) for v in non_empty_first)

    # Build the rows iterable
    if phone_only_no_header:
        all_rows_iter = []
        for raw_row in csv.reader(io.StringIO(decoded)):
            for cell in raw_row:
                if cell.strip():
                    all_rows_iter.append({"phone": cell.strip()})
    elif email_only_no_header:
        all_rows_iter = []
        for raw_row in csv.reader(io.StringIO(decoded)):
            for cell in raw_row:
                if cell.strip():
                    all_rows_iter.append({"email": cell.strip()})
    else:
        reader = csv.DictReader(io.StringIO(decoded))
        all_rows_iter = list(reader)

    # ── Import settings ─────────────────────────────────────────────────────
    imported_phone = 0
    imported_email = 0
    skipped_dnc = 0
    skipped_duplicate = 0
    errors = 0
    seen_phones: set = set()
    seen_emails: set = set()

    from app.core.config import get_settings
    settings = get_settings()
    twilio_num = settings.TWILIO_PHONE_NUMBER or ""
    default_prefix = ""
    if twilio_num.startswith("+91"):
        default_prefix = "91"
    elif twilio_num.startswith("+1"):
        default_prefix = "1"

    for row in all_rows_iter:
        try:
            clean_row: dict = {}
            for k, v in row.items():
                if k is not None:
                    clean_row[k.strip().lower()] = (v or "").strip()

            # Resolve email
            email = (
                clean_row.get("email") or
                clean_row.get("email address") or
                clean_row.get("e-mail") or
                next((v for v in clean_row.values() if _is_email_like(v)), "")
            )

            # Resolve phone
            phone_raw = (
                clean_row.get("phone") or
                clean_row.get("phone number") or
                clean_row.get("number") or
                clean_row.get("phone_number") or
                clean_row.get("mobile") or
                clean_row.get("mobile number") or
                clean_row.get("contact") or ""
            )
            if not phone_raw:
                for col_key, col_val in clean_row.items():
                    if col_val and _is_phone_like(col_val) and not _is_email_like(col_val):
                        phone_raw = col_val
                        break

            # Resolve other fields
            full_name = (
                clean_row.get("name") or clean_row.get("full name") or
                clean_row.get("prospect name") or clean_row.get("contact name") or ""
            )
            business_name = (
                clean_row.get("business") or clean_row.get("business name") or
                clean_row.get("company") or clean_row.get("company name") or
                clean_row.get("organization") or ""
            )
            website = clean_row.get("website") or clean_row.get("site") or clean_row.get("url") or ""
            business_type = clean_row.get("business type") or clean_row.get("industry") or clean_row.get("category") or ""
            city = clean_row.get("city") or clean_row.get("location") or ""
            state = clean_row.get("state") or clean_row.get("region") or ""

            if not phone_raw and not email:
                errors += 1
                continue

            # PATH A: Has phone number
            if phone_raw:
                has_plus = phone_raw.strip().startswith("+")
                digits = ''.join(filter(str.isdigit, phone_raw))
                if not digits or len(digits) < 7:
                    if email:
                        # Fall through to email path
                        phone_raw = ""
                    else:
                        errors += 1
                        continue

            if phone_raw:
                has_plus = phone_raw.strip().startswith("+")
                digits = ''.join(filter(str.isdigit, phone_raw))
                if has_plus:
                    formatted_phone = f"+{digits}"
                elif len(digits) == 10 and default_prefix:
                    formatted_phone = f"+{default_prefix}{digits}"
                elif len(digits) == 12 and default_prefix == "91" and digits.startswith("91"):
                    formatted_phone = f"+{digits}"
                elif len(digits) == 11 and default_prefix == "1" and digits.startswith("1"):
                    formatted_phone = f"+{digits}"
                else:
                    formatted_phone = f"+{digits}"

                if formatted_phone in seen_phones:
                    skipped_duplicate += 1
                    continue
                seen_phones.add(formatted_phone)

                existing = db.query(Lead).filter(Lead.phone == formatted_phone, Lead.is_active == True).first()
                if existing:
                    if campaign_id and existing.campaign_id is None:
                        existing.campaign_id = campaign_id  # type: ignore
                        db.commit()
                    skipped_duplicate += 1
                    continue

                if await is_on_dnc_registry(formatted_phone):
                    skipped_dnc += 1
                    continue

                lead = Lead(
                    full_name=full_name or None,
                    business_name=business_name or None,
                    phone=formatted_phone,
                    email=email or None,
                    website=website or None,
                    business_type=business_type or None,
                    city=city or None,
                    state=state or None,
                    campaign_id=campaign_id,
                    status="pending",
                    source=file.filename[:100] if file.filename else "csv_upload"
                )
                db.add(lead)
                imported_phone += 1
                continue

            # PATH B: Email only (no valid phone)
            if email:
                email_lower = email.lower()
                if email_lower in seen_emails:
                    skipped_duplicate += 1
                    continue
                seen_emails.add(email_lower)

                existing_email = db.query(Lead).filter(
                    Lead.email == email_lower, Lead.is_active == True
                ).first()
                if existing_email:
                    if campaign_id and existing_email.campaign_id is None:
                        existing_email.campaign_id = campaign_id  # type: ignore
                        db.commit()
                    skipped_duplicate += 1
                    continue

                lead = Lead(
                    full_name=full_name or None,
                    business_name=business_name or None,
                    phone=None,
                    email=email_lower,
                    website=website or None,
                    business_type=business_type or None,
                    city=city or None,
                    state=state or None,
                    campaign_id=campaign_id,
                    status="email_only",
                    source=file.filename[:100] if file.filename else "csv_upload"
                )
                db.add(lead)
                imported_email += 1

        except Exception as exc:
            errors += 1

    db.commit()

    total_imported = imported_phone + imported_email
    result: dict = {
        "imported": total_imported,
        "imported_phone": imported_phone,
        "imported_email": imported_email,
        "skipped_duplicate": skipped_duplicate,
        "skipped_dnc": skipped_dnc,
        "errors": errors
    }

    if imported_email > 0 and imported_phone == 0:
        result["info"] = "email_only"
        result["message"] = (
            f"\u2705 Imported {imported_email} email contacts for Email Outreach. "
            "These leads have no phone number so they cannot be called, but are visible in the Leads page."
        )
    elif imported_email > 0 and imported_phone > 0:
        result["message"] = (
            f"\u2705 Imported {imported_phone} callable leads + {imported_email} email-only contacts."
        )

    return result



@router.post("/{lead_id}/approve")
def approve_lead(lead_id: UUID, db: Session = Depends(get_db)):
    """Approve a lead for human-in-the-loop LinkedIn outreach"""
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.is_active == True).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    if lead.linkedin_status == "pending_approval":
        lead.linkedin_status = "approved"  # type: ignore
        db.commit()
        db.refresh(lead)
        return {"message": "Lead approved for outreach", "linkedin_status": lead.linkedin_status}
    else:
        raise HTTPException(status_code=400, detail=f"Lead cannot be approved from current state: {lead.linkedin_status}")


@router.patch("/{lead_id}")
def update_lead(
    lead_id: UUID,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    internal_notes: Optional[str] = None,
    next_call_at: Optional[datetime] = None,
    assigned_to: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Update CRM parameters of a specific lead"""
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.is_active == True).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    if status is not None:
        lead.status = status  # type: ignore
    if priority is not None:
        lead.priority = priority  # type: ignore
    if internal_notes is not None:
        lead.internal_notes = internal_notes  # type: ignore
    if next_call_at is not None:
        lead.next_call_at = next_call_at  # type: ignore
    if assigned_to is not None:
        lead.assigned_to = assigned_to
        
    db.commit()
    db.refresh(lead)
    return lead

@router.delete("/{lead_id}")
def delete_lead(lead_id: UUID, db: Session = Depends(get_db)):
    """Soft delete lead"""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.is_active = False  # type: ignore
    db.commit()
    return {"message": "Lead soft deleted successfully"}

@router.post("/{lead_id}/notes")
def add_lead_note(lead_id: UUID, note: str = Query(...), db: Session = Depends(get_db)):
    """Append timed note to lead internal notes"""
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.is_active == True).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_note = f"\n[{timestamp}] {note}"
    
    if lead.internal_notes:
        lead.internal_notes += formatted_note  # type: ignore
    else:
        lead.internal_notes = formatted_note.strip()  # type: ignore
        
    db.commit()
    db.refresh(lead)
    return lead

# ─── SCREENSHOT DETAILS EXTRACTOR INTEGRATION ───

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "business_name": {
            "type": "string",
            "description": "The name of the business/company. Strip trailing numbers or CIDs."
        },
        "website": {
            "type": "string",
            "description": "The business website domain."
        },
        "poc_name": {
            "type": "string",
            "description": "Person of contact names. If multiple, separate with a comma."
        },
        "phone_number": {
            "type": "string",
            "description": "Phone numbers. If multiple, separate with a comma."
        },
        "email": {
            "type": "string",
            "description": "Email addresses. If multiple, separate with a comma."
        },
        "google_ads_account_cid": {
            "type": "string",
            "description": "The 9 or 10 digit Google Ads Customer ID (CID). If not found, use '--'."
        },
        "last_spoken_google_wrap_name": {
            "type": "string",
            "description": "The name of the Google representative who last made contact."
        },
        "remarks": {
            "type": "string",
            "description": "Any relevant team notes or call remarks."
        }
    },
    "required": [
        "business_name",
        "website",
        "poc_name",
        "phone_number",
        "email",
        "google_ads_account_cid",
        "last_spoken_google_wrap_name",
        "remarks"
    ]
}

SYSTEM_INSTRUCTION = """
You are a precise data extraction assistant. Your task is to extract lead details from screenshots of a Google Ads CRM interface.
Analyze the screenshot carefully. Note that the image may be rotated sideways; read the text in whatever orientation it appears.
Extract fields precisely.
"""

@router.post("/extract-screenshots")
async def extract_lead_from_screenshots(
    files: List[UploadFile] = File(...),
    campaign_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Accept multiple screenshot images, call Gemini to extract structured lead details, 
    merge duplicates, and save to database.
    """
    from app.core.config import get_settings
    from PIL import Image
    import json
    from google import genai
    from google.genai import types
    from app.core.websocket import websocket_manager
    
    settings = get_settings()
    api_key = settings.GEMINI_API_KEY
    
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="GEMINI_API_KEY is not configured in backend settings. Please set it in your .env file."
        )
        
    client = genai.Client(api_key=api_key)
    
    success_count = 0
    errors_count = 0
    results = []
    
    for upload_file in files:
        try:
            # Read and verify image
            contents = await upload_file.read()
            image = Image.open(io.BytesIO(contents))
            
            # Send to Gemini
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[  # type: ignore
                    "Extract all available lead details from this Google Ads CRM screenshot.",
                    image
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RESPONSE_SCHEMA,
                    system_instruction=SYSTEM_INSTRUCTION
                )
            )
            
            if not response.text:
                errors_count += 1
                continue
                
            data = json.loads(response.text)
            
            business = str(data.get("business_name", "")).strip()
            website = str(data.get("website", "")).strip()
            poc = str(data.get("poc_name", "")).strip()
            phone_raw = str(data.get("phone_number", "")).strip()
            email = str(data.get("email", "")).strip()
            cid = str(data.get("google_ads_account_cid", "")).strip()
            google_rep = str(data.get("last_spoken_google_wrap_name", "")).strip()
            remarks = str(data.get("remarks", "")).strip()
            
            if not business and not phone_raw:
                errors_count += 1
                continue
                
            # Smart phone cleaning and formatting for the first phone number
            formatted_phone = "+1000000000"
            first_phone = phone_raw.split(",")[0].strip()
            digits = ''.join(filter(str.isdigit, first_phone))
            if digits:
                if len(digits) == 10:
                    formatted_phone = f"+1{digits}"
                else:
                    formatted_phone = f"+{digits}"
            
            # Look for existing lead
            existing = None
            if formatted_phone != "+1000000000":
                existing = db.query(Lead).filter(
                    Lead.phone == formatted_phone,
                    Lead.is_active == True
                ).first()
                
            if not existing and business:
                business_lower = business.lower()
                existing = db.query(Lead).filter(
                    Lead.business_name.ilike(business_lower),
                    Lead.is_active == True
                ).first()
                
            if existing:
                # Merge details
                if not existing.full_name and poc:
                    existing.full_name = poc  # type: ignore
                if email:
                    existing.email = email if not existing.email else f"{existing.email}, {email}"  # type: ignore
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                notes_addon = f"[AI Screenshot Extraction - {timestamp}]\n"
                if cid and cid != "--":
                    notes_addon += f"- Google Ads CID: {cid}\n"
                if google_rep:
                    notes_addon += f"- Last Google Rep: {google_rep}\n"
                if phone_raw:
                    notes_addon += f"- Extracted Phone(s): {phone_raw}\n"
                if remarks:
                    notes_addon += f"- Remarks: {remarks}\n"
                
                if existing.internal_notes:
                    existing.internal_notes = notes_addon + "\n" + existing.internal_notes  # type: ignore
                else:
                    existing.internal_notes = notes_addon  # type: ignore
                    
                db.commit()
                results.append({
                    "business_name": business,
                    "status": "merged",
                    "lead_id": str(existing.id),
                    "website": website or existing.website,
                    "email": email or existing.email
                })
            else:
                # Create new lead
                notes_body = f"[AI Screenshot Extraction]\n"
                if cid and cid != "--":
                    notes_body += f"- Google Ads CID: {cid}\n"
                if google_rep:
                    notes_body += f"- Last Google Rep: {google_rep}\n"
                if phone_raw:
                    notes_body += f"- Extracted Phone(s): {phone_raw}\n"
                if remarks:
                    notes_body += f"- Remarks: {remarks}\n"
                    
                new_lead = Lead(
                    full_name=poc or "Prospect Name",
                    business_name=business or "Business Name",
                    phone=formatted_phone,
                    email=email or None,
                    website=website or None,
                    campaign_id=campaign_id,
                    source=f"screenshot_{upload_file.filename[:30]}" if upload_file.filename else "screenshot_extraction",
                    internal_notes=notes_body,
                    status="pending"
                )
                db.add(new_lead)
                db.commit()
                db.refresh(new_lead)
                results.append({
                    "business_name": business,
                    "status": "created",
                    "lead_id": str(new_lead.id),
                    "website": website,
                    "email": email
                })
                
            success_count += 1
            
            # Broadcast WebSocket notification so the CRM UI updates live
            await websocket_manager.broadcast({
                "event": "lead_status_updated",
                "lead_id": results[-1]["lead_id"],
                "status": "pending",
                "business_name": business
            })
            
        except Exception as e:
            errors_count += 1
            
    return {
        "success": True,
        "processed": len(files),
        "imported": success_count,
        "errors": errors_count,
        "results": results
    }
