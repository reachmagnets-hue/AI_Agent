from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, desc, func, case
from typing import List, Optional
from datetime import datetime, date, timedelta
from uuid import UUID
from app.utils.timezone import get_ist_today_start, get_ist_yesterday_start, get_ist_yesterday_end
import csv
import io

from app.core.database import get_db
from app.models.lead import Lead
from app.models.call import Call
from app.models.appointment import Appointment
from app.models.campaign import Campaign
from app.utils.dnc import is_on_dnc_registry

router = APIRouter(prefix="/leads", tags=["leads"])

from fastapi.responses import StreamingResponse

# ─── STATIC ROUTES FIRST (before any /{lead_id} dynamic routes) ───────────────

@router.get("/industries")
def get_lead_industries(source: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """Retrieve distinct active canonical industries (business_types) from leads table, optionally filtered by source"""
    from app.utils.industry_normalizer import normalize_industry_name
    query = db.query(Lead.business_type).filter(
        Lead.business_type.isnot(None),
        Lead.business_type != "",
        Lead.is_active == True
    )
    
    if source and source.lower() != "all":
        s_low = source.lower()
        if s_low in ["gmaps", "google_maps", "google_maps_scrape"]:
            query = query.filter(Lead.source == "google_maps_scrape")
        elif s_low in ["screenshot", "screenshot_extract", "ocr"]:
            query = query.filter(or_(Lead.source == "screenshot_extract", Lead.source == "screenshot_ocr", Lead.internal_notes.ilike("%screenshot%")))
        elif s_low in ["csv", "csv_import", "csv_upload"]:
            query = query.filter(or_(Lead.source == "csv_import", Lead.source == "csv_upload", Lead.source.ilike("%.csv%")))
        elif s_low in ["linkedin", "linkedin_prospect", "linkedin_autopilot"]:
            query = query.filter(or_(Lead.source == "linkedin_autopilot", Lead.source == "linkedin_scrape", Lead.source == "linkedin_prospect"))
        else:
            query = query.filter(Lead.source == source)
            
    results = query.distinct().all()
    canonical_set = set()
    for r in results:
        if r[0]:
            canonical_set.add(normalize_industry_name(r[0]))
            
    return {"industries": sorted(list(canonical_set))}

@router.get("/export/csv")
def export_leads_csv(
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
    has_social: Optional[bool] = Query(None),
    has_email: Optional[bool] = Query(None),
    has_phone: Optional[bool] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db)
):
    """Export filtered leads as a CSV download"""
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

    if has_social is not None:
        if has_social:
            query = query.filter(
                or_(
                    Lead.facebook_url.isnot(None),
                    Lead.instagram_url.isnot(None),
                    Lead.linkedin_url.isnot(None),
                    Lead.twitter_url.isnot(None),
                    Lead.youtube_url.isnot(None)
                )
            )
        else:
            query = query.filter(
                and_(
                    Lead.facebook_url.is_(None),
                    Lead.instagram_url.is_(None),
                    Lead.linkedin_url.is_(None),
                    Lead.twitter_url.is_(None),
                    Lead.youtube_url.is_(None)
                )
            )
            
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

    query = query.options(joinedload(Lead.campaign))
    
    sort_column = getattr(Lead, sort_by, Lead.created_at)
    if sort_order.lower() == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)

    leads = query.all()

    # Generate CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        "Business Name", "Full Name", "Phone", "Email", "Website", 
        "Facebook URL", "Instagram URL", "LinkedIn URL", "Twitter URL", "YouTube URL",
        "Directory Profiles & Notes", "Rating", "Description", "Status", "Priority", "Campaign"
    ])
    
    for lead in leads:
        writer.writerow([
            lead.business_name or "",
            lead.full_name or "",
            lead.phone or "",
            lead.email or "",
            lead.website or "",
            lead.facebook_url or "",
            lead.instagram_url or "",
            lead.linkedin_url or "",
            lead.twitter_url or "",
            lead.youtube_url or "",
            lead.internal_notes or "",
            lead.rating or "",
            lead.description or "",
            lead.status or "",
            lead.priority or "",
            lead.campaign.name if lead.campaign else ""
        ])
        
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reach_magnet_leads.csv"}
    )

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
    
    # Daily counts (IST-aware — VPS runs UTC but users are in IST)
    today_start = get_ist_today_start()
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

@router.get("/counts")
def get_lead_counts(db: Session = Depends(get_db)):
    """Get total lead counts for campaign creation UI including extraction date breakdowns"""
    # IST-aware day boundaries — VPS runs UTC but user's calendar day is IST
    today_start = get_ist_today_start()
    yesterday_start = get_ist_yesterday_start()
    yesterday_end = get_ist_yesterday_end()

    total = db.query(func.count(Lead.id)).filter(Lead.is_active == True).scalar() or 0
    with_email = db.query(func.count(Lead.id)).filter(
        Lead.is_active == True,
        Lead.email.isnot(None),
        Lead.email != ""
    ).scalar() or 0
    with_phone = db.query(func.count(Lead.id)).filter(
        Lead.is_active == True,
        Lead.phone.isnot(None),
        Lead.phone != ""
    ).scalar() or 0
    unassigned = db.query(func.count(Lead.id)).filter(
        Lead.is_active == True,
        Lead.campaign_id.is_(None)
    ).scalar() or 0

    extracted_today = db.query(func.count(Lead.id)).filter(
        Lead.is_active == True,
        Lead.created_at >= today_start
    ).scalar() or 0

    extracted_yesterday = db.query(func.count(Lead.id)).filter(
        Lead.is_active == True,
        Lead.created_at >= yesterday_start,
        Lead.created_at <= yesterday_end
    ).scalar() or 0

    unsent_email_today = db.query(func.count(Lead.id)).filter(
        Lead.is_active == True,
        Lead.email.isnot(None),
        Lead.email != "",
        Lead.created_at >= today_start,
        Lead.email_sent_at.is_(None)
    ).scalar() or 0

    unsent_email_yesterday = db.query(func.count(Lead.id)).filter(
        Lead.is_active == True,
        Lead.email.isnot(None),
        Lead.email != "",
        Lead.created_at >= yesterday_start,
        Lead.created_at <= yesterday_end,
        Lead.email_sent_at.is_(None)
    ).scalar() or 0

    unsent_email_all = db.query(func.count(Lead.id)).filter(
        Lead.is_active == True,
        Lead.email.isnot(None),
        Lead.email != "",
        Lead.email_sent_at.is_(None)
    ).scalar() or 0

    return {
        "total": total,
        "with_email": with_email,
        "with_phone": with_phone,
        "unassigned": unassigned,
        "extracted_today": extracted_today,
        "extracted_yesterday": extracted_yesterday,
        "unsent_email_today": unsent_email_today,
        "unsent_email_yesterday": unsent_email_yesterday,
        "unsent_email_all": unsent_email_all
    }

@router.get("/")
@router.get("")
def get_leads(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    campaign_id: Optional[str] = Query(None),
    business_type: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    called_from: Optional[date] = Query(None),
    called_to: Optional[date] = Query(None),
    has_meeting: Optional[bool] = Query(None),
    no_answer: Optional[bool] = Query(None),
    has_linkedin: Optional[bool] = Query(None),
    has_social: Optional[bool] = Query(None),
    has_email: Optional[bool] = Query(None),
    has_phone: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=1000),
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
    if business_type and business_type.lower() != "all":
        query = query.filter(Lead.business_type == "Auto Body Shop")
    if priority:
        query = query.filter(Lead.priority == priority)
        
    if source and source.lower() != "all":
        s_low = source.lower()
        if s_low in ["gmaps", "google_maps", "google_maps_scrape"]:
            query = query.filter(Lead.source == "google_maps_scrape")
        elif s_low in ["screenshot", "screenshot_extract", "ocr"]:
            query = query.filter(or_(Lead.source == "screenshot_extract", Lead.source == "screenshot_ocr", Lead.internal_notes.ilike("%screenshot%")))
        elif s_low in ["csv", "csv_import", "csv_upload"]:
            query = query.filter(or_(Lead.source == "csv_import", Lead.source == "csv_upload", Lead.source.ilike("%.csv%")))
        elif s_low in ["linkedin", "linkedin_prospect", "linkedin_autopilot"]:
            query = query.filter(or_(Lead.source == "linkedin_autopilot", Lead.source == "linkedin_scrape", Lead.source == "linkedin_prospect"))
        else:
            query = query.filter(Lead.source == source)
        
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

    if has_social is not None:
        if has_social:
            query = query.filter(
                or_(
                    Lead.facebook_url.isnot(None),
                    Lead.instagram_url.isnot(None),
                    Lead.linkedin_url.isnot(None),
                    Lead.twitter_url.isnot(None),
                    Lead.youtube_url.isnot(None)
                )
            )
        else:
            query = query.filter(
                and_(
                    Lead.facebook_url.is_(None),
                    Lead.instagram_url.is_(None),
                    Lead.linkedin_url.is_(None),
                    Lead.twitter_url.is_(None),
                    Lead.youtube_url.is_(None)
                )
            )
            
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

        except Exception as row_err:
            errors += 1
            continue

    db.commit()

    return {
        "imported_phone": imported_phone,
        "imported_email": imported_email,
        "skipped_duplicate": skipped_duplicate,
        "skipped_dnc": skipped_dnc,
        "errors": errors,
        "total_imported": imported_phone + imported_email
    }

@router.patch("/{lead_id}")
def update_lead(
    lead_id: UUID,
    full_name: Optional[str] = None,
    business_name: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    website: Optional[str] = None,
    business_type: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    campaign_id: Optional[UUID] = None,
    internal_notes: Optional[str] = None,
    is_dnc: Optional[bool] = None,
    linkedin_url: Optional[str] = None,
    facebook_url: Optional[str] = None,
    instagram_url: Optional[str] = None,
    twitter_url: Optional[str] = None,
    youtube_url: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Update a lead's profile fields"""
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.is_active == True).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    if full_name is not None:
        lead.full_name = full_name  # type: ignore
    if business_name is not None:
        lead.business_name = business_name  # type: ignore
    if phone is not None:
        lead.phone = phone  # type: ignore
    if email is not None:
        lead.email = email  # type: ignore
    if website is not None:
        lead.website = website  # type: ignore
    if business_type is not None:
        lead.business_type = business_type  # type: ignore
    if city is not None:
        lead.city = city  # type: ignore
    if state is not None:
        lead.state = state  # type: ignore
    if status is not None:
        lead.status = status  # type: ignore
    if priority is not None:
        lead.priority = priority  # type: ignore
    if campaign_id is not None:
        lead.campaign_id = campaign_id  # type: ignore
    if internal_notes is not None:
        lead.internal_notes = internal_notes  # type: ignore
    if is_dnc is not None:
        lead.is_dnc = is_dnc  # type: ignore
    if linkedin_url is not None:
        lead.linkedin_url = linkedin_url  # type: ignore
    if facebook_url is not None:
        lead.facebook_url = facebook_url  # type: ignore
    if instagram_url is not None:
        lead.instagram_url = instagram_url  # type: ignore
    if twitter_url is not None:
        lead.twitter_url = twitter_url  # type: ignore
    if youtube_url is not None:
        lead.youtube_url = youtube_url  # type: ignore

    db.commit()
    db.refresh(lead)
    return lead

@router.delete("/{lead_id}")
def delete_lead(lead_id: UUID, db: Session = Depends(get_db)):
    """Soft-delete a lead (sets is_active = False)"""
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.is_active == True).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.is_active = False  # type: ignore
    db.commit()
    return {"message": "Lead deleted successfully"}

# ─── DYNAMIC ROUTE LAST — must come after all static routes ───────────────────

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
    
    if lead.email_sent_at:
        timeline.append({
            "type": "email",
            "title": f"Outreach Email to {lead.email or 'N/A'}",
            "time": lead.email_sent_at,
            "detail": f"Status: {lead.email_status or 'sent'} | "
                      f"Delivered: {lead.email_delivered_at.strftime('%Y-%m-%d %H:%M:%S') if lead.email_delivered_at else 'No'} | "
                      f"Opened: {lead.email_opened_at.strftime('%Y-%m-%d %H:%M:%S') if lead.email_opened_at else 'No'} | "
                      f"Clicked: {lead.email_clicked_at.strftime('%Y-%m-%d %H:%M:%S') if lead.email_clicked_at else 'No'} | "
                      f"Bounced: {lead.email_bounced_at.strftime('%Y-%m-%d %H:%M:%S') if lead.email_bounced_at else 'No'} | "
                      f"Blocked: {lead.email_blocked_at.strftime('%Y-%m-%d %H:%M:%S') if lead.email_blocked_at else 'No'}"
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
