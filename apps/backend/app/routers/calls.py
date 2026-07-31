from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func, cast, String, text
from typing import List, Optional
from datetime import datetime, date, timedelta
from app.utils.timezone import get_ist_today_start
from uuid import UUID

from app.core.database import get_db
from app.models.call import Call
from app.models.lead import Lead
from app.models.appointment import Appointment
from app.models.campaign import Campaign

router = APIRouter(prefix="/calls", tags=["calls"])

@router.get("/")
@router.get("")
def get_calls(
    lead_id: Optional[UUID] = Query(None),
    campaign_id: Optional[UUID] = Query(None),
    outcome: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    duration_min: Optional[int] = Query(None),
    duration_max: Optional[int] = Query(None),
    has_transcript: Optional[bool] = Query(None),
    has_meeting: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db)
):
    """GET call logs with advanced filtering options"""
    query = db.query(Call).join(Lead, Call.lead_id == Lead.id)
    
    if lead_id:
        query = query.filter(Call.lead_id == lead_id)
    if campaign_id:
        query = query.filter(Call.campaign_id == campaign_id)
    outcome_filter = None
    if outcome:
        outcomes = [o.strip() for o in outcome.split(',')]
        outcome_filter = Call.outcome.in_(outcomes)
        
    status_filter = None
    if status:
        statuses = [s.strip() for s in status.split(',')]
        status_filter = Call.status.in_(statuses)
        
    if outcome_filter is not None and status_filter is not None:
        query = query.filter(or_(outcome_filter, status_filter))
    elif outcome_filter is not None:
        query = query.filter(outcome_filter)
    elif status_filter is not None:
        query = query.filter(status_filter)
        
    if date_from:
        query = query.filter(Call.started_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        query = query.filter(Call.started_at <= datetime.combine(date_to, datetime.max.time()))
        
    if duration_min:
        query = query.filter(Call.duration_seconds >= duration_min)
    if duration_max:
        query = query.filter(Call.duration_seconds <= duration_max)
        
    if has_transcript is not None:
        if has_transcript:
            query = query.filter(Call.transcript.isnot(None), Call.transcript != "")
        else:
            query = query.filter(or_(Call.transcript.is_(None), Call.transcript == ""))
            
    if has_meeting is not None:
        query = query.filter(Call.meeting_booked == has_meeting)
        
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Call.transcript.ilike(search_filter),
                Lead.full_name.ilike(search_filter),
                Lead.business_name.ilike(search_filter)
            )
        )

    # Sort
    sort_column = getattr(Call, sort_by, Call.created_at)
    if sort_order.lower() == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)

    total = query.count()
    pages = (total + limit - 1) // limit
    calls = query.offset((page - 1) * limit).limit(limit).all()

    # Build return payload containing call and lead snapshot info
    calls_data = []
    for call in calls:
        calls_data.append({
            "id": call.id,
            "lead_id": call.lead_id,
            "campaign_id": call.campaign_id,
            "retell_call_id": call.retell_call_id,
            "twilio_call_sid": call.twilio_call_sid,
            "from_number": call.from_number,
            "to_number": call.to_number,
            "started_at": call.started_at,
            "ended_at": call.ended_at,
            "duration_seconds": call.duration_seconds,
            "status": call.status,
            "outcome": call.outcome,
            "transcript": call.transcript,
            "ai_summary": call.ai_summary,
            "sentiment": call.sentiment,
            "objection_raised": call.objection_raised,
            "meeting_booked": call.meeting_booked,
            "sms_sent": call.sms_sent,
            "email_sent": call.email_sent,
            "voicemail_dropped": call.voicemail_dropped,
            "recording_url": call.recording_url,
            "attempt_number": call.attempt_number,
            "created_at": call.created_at,
            "lead": {
                "id": call.lead.id,
                "full_name": call.lead.full_name,
                "business_name": call.lead.business_name,
                "phone": call.lead.phone,
                "status": call.lead.status
            }
        })

    return {
        "calls": calls_data,
        "total": total,
        "page": page,
        "pages": pages
    }

@router.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Retrieve summarized analytics for the main dashboard"""
    from app.utils.timezone import get_ist_today_start, get_ist_yesterday_start, get_ist_yesterday_end
    from datetime import timedelta, timezone as dt_timezone

    ist_tz = dt_timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(dt_timezone.utc).astimezone(ist_tz)

    # IST-aware day boundaries (naive UTC datetimes for SQLAlchemy)
    today_dt      = get_ist_today_start()
    yesterday_dt  = get_ist_yesterday_start()
    yesterday_end = get_ist_yesterday_end()

    # IST date strings for the 7-day rolling window (cast+like is fine for ranges)
    seven_days_ago_str = (now_ist.date() - timedelta(days=7)).strftime("%Y-%m-%d")

    # ─── Total Contacts ───────────────────────────────────────────────────────
    total_contacts = db.query(Lead).filter(Lead.is_active == True).count()

    # ─── Leads extracted today / yesterday ───────────────────────────────────
    leads_today = db.query(Lead).filter(
        Lead.is_active == True,
        Lead.created_at >= today_dt
    ).count()
    leads_yesterday = db.query(Lead).filter(
        Lead.is_active == True,
        Lead.created_at >= yesterday_dt,
        Lead.created_at <= yesterday_end
    ).count()

    # ─── Campaigns ───────────────────────────────────────────────────────────
    total_campaigns = db.query(Campaign).count()

    # ─── Calls ───────────────────────────────────────────────────────────────
    total_calls = db.query(Call).count()
    calls_today = db.query(Call).filter(
        Call.created_at >= today_dt
    ).count()
    calls_yesterday = db.query(Call).filter(
        Call.created_at >= yesterday_dt,
        Call.created_at <= yesterday_end
    ).count()
    failed_calls = db.query(Call).filter(
        Call.status.in_(["failed", "busy", "no-answer"])
    ).count()
    pending_calls = db.query(Lead).filter(
        Lead.is_active == True, Lead.status == "pending"
    ).count()

    total_completed = db.query(Call).filter(Call.status == "completed").count()
    total_meetings  = db.query(Call).filter(Call.meeting_booked == True).count()

    success_rate = 0.0
    if total_completed > 0:
        success_rate = round((total_meetings / total_completed) * 100.0, 1)
    elif total_calls > 0:
        success_rate = round((total_meetings / total_calls) * 100.0, 1)

    # ─── Email Stats ─────────────────────────────────────────────────────────
    email_sent = db.query(Lead).filter(
        Lead.is_active == True,
        or_(Lead.email_sent_at.isnot(None), Lead.email_status.isnot(None))
    ).count()
    email_sent_today = db.query(Lead).filter(
        Lead.is_active == True,
        Lead.email_sent_at >= today_dt
    ).count()
    email_sent_yesterday = db.query(Lead).filter(
        Lead.is_active == True,
        Lead.email_sent_at >= yesterday_dt,
        Lead.email_sent_at <= yesterday_end
    ).count()
    email_bounced = db.query(Lead).filter(
        Lead.is_active == True,
        or_(Lead.email_status == "bounced", Lead.email_bounced_at.isnot(None))
    ).count()
    email_blocked = db.query(Lead).filter(
        Lead.is_active == True,
        or_(Lead.email_status == "blocked", Lead.email_blocked_at.isnot(None))
    ).count()
    email_delivered = db.query(Lead).filter(
        Lead.is_active == True,
        Lead.email_sent_at.isnot(None),
        Lead.email_status.notin_(["bounced", "blocked"])
    ).count()
    email_opened = db.query(Lead).filter(
        Lead.is_active == True,
        or_(Lead.email_status.in_(["opened", "clicked", "replied"]), Lead.email_opened_at.isnot(None))
    ).count()
    email_clicked = db.query(Lead).filter(
        Lead.is_active == True,
        or_(Lead.email_status.in_(["clicked", "replied"]), Lead.email_clicked_at.isnot(None))
    ).count()
    email_replied = db.query(Lead).filter(
        Lead.is_active == True, Lead.email_status == "replied"
    ).count()
    email_pending = db.query(Lead).filter(
        Lead.is_active == True,
        Lead.email.isnot(None),
        Lead.email != "",
        Lead.email_sent_at.is_(None)
    ).count()
    # Real bounce messages from DB (not hardcoded)
    raw_bounce_messages = db.query(Lead).filter(
        Lead.is_active == True,
        Lead.email_bounced_at.isnot(None)
    ).count()

    # ─── LinkedIn Stats ───────────────────────────────────────────────────────
    linkedin_sent = db.query(Lead).filter(
        Lead.is_active == True,
        or_(Lead.linkedin_sent_at.isnot(None),
            Lead.linkedin_status.in_(["connection_sent", "connected", "message_sent", "meeting_scheduled"]))
    ).count()
    linkedin_sent_today = db.query(Lead).filter(
        Lead.is_active == True,
        Lead.linkedin_sent_at >= today_dt
    ).count()
    linkedin_sent_yesterday = db.query(Lead).filter(
        Lead.is_active == True,
        Lead.linkedin_sent_at >= yesterday_dt,
        Lead.linkedin_sent_at <= yesterday_end
    ).count()
    linkedin_connected = db.query(Lead).filter(
        Lead.is_active == True,
        Lead.linkedin_status.in_(["connected", "message_sent", "meeting_scheduled"])
    ).count()
    linkedin_messages_sent = db.query(Lead).filter(
        Lead.is_active == True,
        Lead.linkedin_status.in_(["message_sent", "meeting_scheduled"])
    ).count()
    linkedin_replied = db.query(Lead).filter(
        Lead.is_active == True,
        Lead.linkedin_status == "meeting_scheduled"
    ).count()

    # ─── Extraction & Directory Enrichment ───────────────────────────────────
    directories_extracted = db.query(Lead).filter(
        or_(
            Lead.internal_notes.like("%[Directories]%"),
            Lead.internal_notes.like("%yelp%"),
            Lead.internal_notes.like("%bbb%"),
            Lead.internal_notes.like("%nextdoor%"),
            Lead.internal_notes.like("%yellowpages%"),
            Lead.facebook_url.isnot(None),
            Lead.instagram_url.isnot(None),
            Lead.linkedin_url.isnot(None),
            Lead.twitter_url.isnot(None),
            Lead.youtube_url.isnot(None)
        )
    ).count()
    leads_with_emails = db.query(Lead).filter(
        Lead.email.isnot(None), Lead.email != ""
    ).count()
    leads_with_socials = db.query(Lead).filter(
        or_(
            Lead.facebook_url.isnot(None),
            Lead.instagram_url.isnot(None),
            Lead.linkedin_url.isnot(None),
            Lead.twitter_url.isnot(None),
            Lead.youtube_url.isnot(None)
        )
    ).count()
    total_extracted = db.query(Lead).filter(
        Lead.is_active == True,
        or_(
            Lead.source.in_(["google_maps_scrape", "linkedin_scraper", "scraper"]),
            Lead.internal_notes.like("%scraped%"),
            Lead.internal_notes.like("%extracted%")
        )
    ).count()

    # ─── Bookings ─────────────────────────────────────────────────────────────
    total_bookings = db.query(Appointment).count()
    bookings_today = db.query(Appointment).filter(
        Appointment.created_at >= today_dt
    ).count()

    # ── LAST ACTIVE DAY fallback ──────────────────────────────────────────────
    # When today shows 0, find the most recent day with real data.
    # Uses IST-offset adjusted dates stored as UTC naive strings.
    last_active_leads_date  = None
    last_active_leads_count = 0
    last_active_email_date  = None
    last_active_email_count = 0
    last_active_calls_date  = None
    last_active_calls_count = 0

    if leads_today == 0:
        # Find most recent day with any lead; convert UTC date back to IST date
        row = db.execute(
            text("""
                SELECT date(datetime(created_at, '+5 hours', '+30 minutes')) as d,
                       count(*) as c
                FROM leads WHERE is_active=1 AND created_at IS NOT NULL
                GROUP BY d ORDER BY d DESC LIMIT 1
            """)
        ).fetchone()
        if row:
            last_active_leads_date  = row[0]
            last_active_leads_count = row[1]

    if email_sent_today == 0:
        row = db.execute(
            text("""
                SELECT date(datetime(email_sent_at, '+5 hours', '+30 minutes')) as d,
                       count(*) as c
                FROM leads WHERE email_sent_at IS NOT NULL AND is_active=1
                GROUP BY d ORDER BY d DESC LIMIT 1
            """)
        ).fetchone()
        if row:
            last_active_email_date  = row[0]
            last_active_email_count = row[1]

    if calls_today == 0:
        row = db.execute(
            text("""
                SELECT date(datetime(started_at, '+5 hours', '+30 minutes')) as d,
                       count(*) as c
                FROM calls WHERE started_at IS NOT NULL
                GROUP BY d ORDER BY d DESC LIMIT 1
            """)
        ).fetchone()
        if row:
            last_active_calls_date  = row[0]
            last_active_calls_count = row[1]

    # 7-day rolling window stats
    seven_days_ago_dt = today_dt - timedelta(days=7)
    leads_7d = db.query(Lead).filter(
        Lead.is_active == True,
        Lead.created_at >= seven_days_ago_dt
    ).count()
    calls_7d = db.query(Call).filter(
        Call.created_at >= seven_days_ago_dt
    ).count()
    email_sent_7d = db.query(Lead).filter(
        Lead.is_active == True,
        Lead.email_sent_at.isnot(None),
        Lead.email_sent_at >= seven_days_ago_dt
    ).count()

    return {
        "totalContacts":        total_contacts,
        "leadsToday":           leads_today,
        "leadsYesterday":       leads_yesterday,
        "totalCampaigns":       total_campaigns,
        "totalCalls":           total_calls,
        "callsToday":           calls_today,
        "callsYesterday":       calls_yesterday,
        "successRate":          success_rate,
        "pendingCalls":         pending_calls,
        "failedCalls":          failed_calls,
        # Email
        "emailSent":            email_sent,
        "emailSentToday":       email_sent_today,
        "emailSentYesterday":   email_sent_yesterday,
        "emailDelivered":       email_delivered,
        "emailOpened":          email_opened,
        "emailClicked":         email_clicked,
        "emailReplied":         email_replied,
        "emailBounced":         email_bounced,
        "rawBounceMessages":    raw_bounce_messages,
        "emailBlocked":         email_blocked,
        "emailPending":         email_pending,
        # LinkedIn
        "linkedinSent":         linkedin_sent,
        "linkedinSentToday":    linkedin_sent_today,
        "linkedinSentYesterday": linkedin_sent_yesterday,
        "linkedinConnected":    linkedin_connected,
        "linkedinMessagesSent": linkedin_messages_sent,
        "linkedinReplied":      linkedin_replied,
        # Extraction & Enrichment
        "directoriesExtracted": directories_extracted,
        "totalExtracted":       total_extracted,
        "leadsWithEmails":      leads_with_emails,
        "leadsWithSocials":     leads_with_socials,
        # Bookings
        "totalBookings":        total_bookings,
        "bookingsToday":        bookings_today,
        # Last-active-day fallback (populated when today = 0)
        "lastActiveLeadsDate":  last_active_leads_date,
        "lastActiveLeadsCount": last_active_leads_count,
        "lastActiveEmailDate":  last_active_email_date,
        "lastActiveEmailCount": last_active_email_count,
        "lastActiveCallsDate":  last_active_calls_date,
        "lastActiveCallsCount": last_active_calls_count,
        # 7-day rolling window
        "leads7d":              leads_7d,
        "calls7d":              calls_7d,
        "emailSent7d":          email_sent_7d,
    }






@router.get("/stats/overview")
def get_calls_stats_overview(db: Session = Depends(get_db)):
    """Hourly and daily metrics overview report for call logs"""
    from datetime import timezone
    now_utc = datetime.now(timezone.utc)
    today_start = get_ist_today_start()  # IST-aware: VPS runs UTC but user calendar is IST
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    
    # Today metrics
    today_query = db.query(Call).filter(Call.created_at >= today_start)
    today_total = today_query.count()
    today_answered = today_query.filter(Call.status == "completed").count()
    today_booked = today_query.filter(Call.meeting_booked == True).count()
    today_avg_dur = today_query.with_entities(func.avg(Call.duration_seconds)).scalar() or 0.0

    # This week real data
    week_query = db.query(Call).filter(Call.created_at >= week_start)
    week_total = week_query.count()
    week_answered = week_query.filter(Call.status == "completed").count()
    week_booked = week_query.filter(Call.meeting_booked == True).count()
    week_avg_dur = week_query.with_entities(func.avg(Call.duration_seconds)).scalar() or 0.0

    # This month real data
    month_query = db.query(Call).filter(Call.created_at >= month_start)
    month_total = month_query.count()
    month_answered = month_query.filter(Call.status == "completed").count()
    month_booked = month_query.filter(Call.meeting_booked == True).count()
    month_avg_dur = month_query.with_entities(func.avg(Call.duration_seconds)).scalar() or 0.0

    # outcome breakdown (all time)
    outcomes = db.query(Call.outcome, func.count(Call.id)).group_by(Call.outcome).all()
    by_outcome = {o: count for o, count in outcomes if o is not None}

    # hourly activity for today (done in Python to avoid 13 loops)
    today_calls_ts = db.query(Call.created_at).filter(Call.created_at >= today_start).all()
    hourly_counts = {h: 0 for h in range(8, 21)}
    for (created_at,) in today_calls_ts:
        if created_at:
            h = created_at.hour
            if h in hourly_counts:
                hourly_counts[h] += 1
    hourly_calls = [{"hour": h, "calls": count} for h, count in hourly_counts.items()]

    # daily breakdown for this week (done in Python to avoid 14 loops)
    week_calls_ts = db.query(Call.created_at, Call.status).filter(Call.created_at >= week_start).all()
    daily_stats = {i: {"calls": 0, "answered": 0} for i in range(7)}
    for created_at, status in week_calls_ts:
        if created_at:
            day_idx = created_at.weekday()
            if day_idx in daily_stats:
                daily_stats[day_idx]["calls"] += 1
                if status == "completed":
                    daily_stats[day_idx]["answered"] += 1

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    by_day = []
    for i, day_name in enumerate(day_names[:7]):
        stats = daily_stats[i]
        d_total = stats["calls"]
        d_answered = stats["answered"]
        answer_rate = round(d_answered / d_total, 2) if d_total > 0 else 0.0
        by_day.append({"day": day_name, "calls": d_total, "answer_rate": answer_rate})

    return {
        "today": {
            "total": today_total,
            "answered": today_answered,
            "booked": today_booked,
            "avg_duration": round(float(today_avg_dur), 1)
        },
        "this_week": {
            "total": week_total,
            "answered": week_answered,
            "booked": week_booked,
            "avg_duration": round(float(week_avg_dur), 1)
        },
        "this_month": {
            "total": month_total,
            "answered": month_answered,
            "booked": month_booked,
            "avg_duration": round(float(month_avg_dur), 1)
        },
        "by_outcome": by_outcome,
        "by_hour": hourly_calls,
        "by_day": by_day
    }

@router.get("/{call_id}")
def get_call_detail(call_id: UUID, db: Session = Depends(get_db)):
    """Retrieve deep detail page layout for single call log"""
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call record not found")

    # Format transcript lines
    transcript_formatted = []
    if call.transcript:
        lines = call.transcript.split("\n")
        time_offset = 0
        for line in lines:
            if not line.strip(): continue
            speaker = "AI" if ("AI:" in line or "Sarah:" in line or "Alex:" in line or "Ojas:" in line) else "Prospect"
            text = line.replace("AI:", "").replace("Sarah:", "").replace("Alex:", "").replace("Ojas:", "").replace("Prospect:", "").strip()
            
            # Simple simulation of conversation timing
            min_offset = time_offset // 60
            sec_offset = time_offset % 60
            timestamp = f"{min_offset}:{sec_offset:02d}"
            
            transcript_formatted.append({
                "speaker": speaker,
                "text": text,
                "timestamp": timestamp
            })
            time_offset += 6 # assume 6s average exchange length

    # Check for linked appointments
    appt_record = db.query(Appointment).filter(Appointment.call_id == call.id).first()

    return {
        "call": call,
        "lead": {
            "name": call.lead.full_name,
            "phone": call.lead.phone,
            "business": call.lead.business_name,
            "status": call.lead.status
        },
        "transcript_formatted": transcript_formatted,
        "appointment": appt_record
    }

@router.post("/{call_id}/cancel")
def cancel_call_log(call_id: UUID, db: Session = Depends(get_db)):
    """Cancel call log and log state update"""
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    call.status = "failed"  # type: ignore
    call.ended_at = datetime.now()  # type: ignore
    db.commit()
    return {"message": "Call log marked as cancelled"}

@router.delete("/{call_id}")
def delete_call_log(call_id: UUID, db: Session = Depends(get_db)):
    """Delete call log completely"""
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    db.delete(call)
    db.commit()
    return {"message": "Call log permanently deleted"}