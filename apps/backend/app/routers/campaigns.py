from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func, text
from typing import List, Optional
from datetime import datetime, date, timezone
import uuid
from uuid import UUID, uuid4
import structlog

from app.core.database import get_db
from app.models.campaign import Campaign
from app.models.lead import Lead
from app.models.call import Call
from app.models.appointment import Appointment
from app.services.retell_service import RetellService

router = APIRouter(prefix="/campaigns", tags=["campaigns"])
logger = structlog.get_logger(__name__)

@router.get("/")
@router.get("")
def get_campaigns(
    status: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    """GET list of campaigns with summary stats"""
    query = db.query(Campaign)
    if status:
        query = query.filter(Campaign.status == status)
    if date_from:
        query = query.filter(Campaign.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        query = query.filter(Campaign.created_at <= datetime.combine(date_to, datetime.max.time()))
        
    campaigns = query.order_by(desc(Campaign.created_at)).all()
    
    # Pre-calculate totals using aggregate group-by queries to avoid O(N) database loops
    from sqlalchemy import func
    
    leads_counts = db.query(Lead.campaign_id, func.count(Lead.id)).filter(Lead.is_active == True).group_by(Lead.campaign_id).all()
    leads_map = {cid: count for cid, count in leads_counts if cid is not None}
    
    calls_counts = db.query(Call.campaign_id, func.count(Call.id)).group_by(Call.campaign_id).all()
    calls_map = {cid: count for cid, count in calls_counts if cid is not None}
    
    answered_counts = db.query(Call.campaign_id, func.count(Call.id)).filter(Call.status == "completed").group_by(Call.campaign_id).all()
    answered_map = {cid: count for cid, count in answered_counts if cid is not None}
    
    booked_counts = db.query(Appointment.campaign_id, func.count(Appointment.id)).group_by(Appointment.campaign_id).all()
    booked_map = {cid: count for cid, count in booked_counts if cid is not None}
    
    pending_counts = db.query(Lead.campaign_id, func.count(Lead.id)).filter(Lead.status == "pending", Lead.is_active == True).group_by(Lead.campaign_id).all()
    pending_map = {cid: count for cid, count in pending_counts if cid is not None}
    
    unpicked_counts = db.query(Lead.campaign_id, func.count(Lead.id)).filter(Lead.status.in_(["failed", "no_answer", "voicemail", "busy"]), Lead.is_active == True).group_by(Lead.campaign_id).all()
    unpicked_map = {cid: count for cid, count in unpicked_counts if cid is not None}

    # Email Specific Metrics Maps
    email_sent_counts = db.query(Lead.campaign_id, func.count(Lead.id)).filter(Lead.email_sent_at.isnot(None), Lead.is_active == True).group_by(Lead.campaign_id).all()
    email_sent_map = {cid: count for cid, count in email_sent_counts if cid is not None}

    email_delivered_counts = db.query(Lead.campaign_id, func.count(Lead.id)).filter(Lead.email_sent_at.isnot(None), Lead.email_status.notin_(["bounced", "blocked"]), Lead.is_active == True).group_by(Lead.campaign_id).all()
    email_delivered_map = {cid: count for cid, count in email_delivered_counts if cid is not None}

    email_opened_counts = db.query(Lead.campaign_id, func.count(Lead.id)).filter(or_(Lead.email_status.in_(["opened", "clicked", "replied"]), Lead.email_opened_at.isnot(None)), Lead.is_active == True).group_by(Lead.campaign_id).all()
    email_opened_map = {cid: count for cid, count in email_opened_counts if cid is not None}

    email_replied_counts = db.query(Lead.campaign_id, func.count(Lead.id)).filter(Lead.email_status == "replied", Lead.is_active == True).group_by(Lead.campaign_id).all()
    email_replied_map = {cid: count for cid, count in email_replied_counts if cid is not None}

    email_pending_counts = db.query(Lead.campaign_id, func.count(Lead.id)).filter(Lead.email_sent_at.is_(None), Lead.is_active == True).group_by(Lead.campaign_id).all()
    email_pending_map = {cid: count for cid, count in email_pending_counts if cid is not None}
    
    data = []
    for c in campaigns:
        total_leads = leads_map.get(c.id, 0)
        total_called = calls_map.get(c.id, 0)
        total_answered = answered_map.get(c.id, 0)
        total_booked = booked_map.get(c.id, 0)
        total_unpicked = unpicked_map.get(c.id, 0)
        
        email_sent = email_sent_map.get(c.id, 0)
        email_delivered = email_delivered_map.get(c.id, 0)
        email_opened = email_opened_map.get(c.id, 0)
        email_replied = email_replied_map.get(c.id, 0)

        camp_type = getattr(c, "campaign_type", "call") or "call"
        if camp_type == "email":
            total_pending = email_pending_map.get(c.id, max(0, total_leads - email_sent))
        else:
            total_pending = pending_map.get(c.id, 0)
        
        data.append({
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "status": c.status,
            "campaign_type": camp_type,
            "start_time": c.start_time,
            "end_time": c.end_time,
            "timezone": c.timezone,
            "calls_per_minute": c.calls_per_minute,
            "max_attempts": c.max_attempts,
            "ai_script": c.ai_script,
            "ai_persona_name": c.ai_persona_name,
            "total_leads": total_leads,
            "total_called": total_called,
            "total_answered": total_answered,
            "total_booked": total_booked,
            "total_pending": total_pending,
            "total_unpicked": total_unpicked,
            "email_sent": email_sent,
            "email_delivered": email_delivered,
            "email_opened": email_opened,
            "email_replied": email_replied,
            "created_at": c.created_at,
            "started_at": c.started_at,
            "completed_at": c.completed_at
        })
    return data

@router.get("/{campaign_id}")
def get_campaign(campaign_id: UUID, db: Session = Depends(get_db)):
    """Retrieve full campaign overview panel details with conversion funnel stats"""
    campaign = db.query(Campaign).filter(text(f"campaigns.id = '{str(campaign_id)}'")).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    total_leads = db.query(Lead).filter(text(f"leads.campaign_id = '{str(campaign_id)}'")).count()
    called = db.query(Call).filter(text(f"calls.campaign_id = '{str(campaign_id)}'")).count()
    answered = db.query(Call).filter(text(f"calls.campaign_id = '{str(campaign_id)}'"), Call.status == "completed").count()
    interested = db.query(Call).filter(text(f"calls.campaign_id = '{str(campaign_id)}'"), Call.outcome == "interested").count()
    booked = db.query(Appointment).filter(text(f"appointments.campaign_id = '{str(campaign_id)}'")).count()
    no_answer = db.query(Call).filter(text(f"calls.campaign_id = '{str(campaign_id)}'"), Call.status == "no_answer").count()
    
    # Email stats
    email_sent = db.query(Lead).filter(text(f"leads.campaign_id = '{str(campaign_id)}'"), Lead.email_sent_at.isnot(None), Lead.is_active == True).count()
    email_delivered = db.query(Lead).filter(text(f"leads.campaign_id = '{str(campaign_id)}'"), Lead.email_sent_at.isnot(None), Lead.email_status.notin_(["bounced", "blocked"]), Lead.is_active == True).count()
    email_opened = db.query(Lead).filter(text(f"leads.campaign_id = '{str(campaign_id)}'"), or_(Lead.email_status.in_(["opened", "clicked", "replied"]), Lead.email_opened_at.isnot(None)), Lead.is_active == True).count()
    email_replied = db.query(Lead).filter(text(f"leads.campaign_id = '{str(campaign_id)}'"), Lead.email_status == "replied", Lead.is_active == True).count()

    # Cost estimation
    total_duration_sec = db.query(func.sum(Call.duration_seconds)).filter(text(f"calls.campaign_id = '{str(campaign_id)}'")).scalar() or 0
    total_minutes = total_duration_sec / 60.0
    estimated_cost = total_minutes * 0.07 # $0.07/min Retell standard billing
    
    stats = {
        "total_leads": total_leads,
        "called": called,
        "answered": answered,
        "interested": interested,
        "meetings_booked": booked,
        "not_interested": called - answered - no_answer,
        "no_answer": no_answer,
        "answer_rate": round(answered / called * 100.0, 1) if called > 0 else 0.0,
        "conversion_rate": round(booked / answered * 100.0, 1) if answered > 0 else 0.0,
        "avg_call_duration": round(total_duration_sec / called, 1) if called > 0 else 0.0,
        "total_call_minutes": round(total_minutes, 1),
        "estimated_cost": round(estimated_cost, 2),
        "email_sent": email_sent,
        "email_delivered": email_delivered,
        "email_opened": email_opened,
        "email_replied": email_replied
    }

    # Fetch last 10 calls
    recent_calls = db.query(Call).filter(text(f"calls.campaign_id = '{str(campaign_id)}'")).order_by(desc(Call.created_at)).limit(10).all()
    # Fetch last 5 appointments
    recent_bookings = db.query(Appointment).filter(text(f"appointments.campaign_id = '{str(campaign_id)}'")).order_by(desc(Appointment.created_at)).limit(5).all()

    return {
        "campaign": campaign,
        "stats": stats,
        "recent_calls": recent_calls,
        "recent_bookings": recent_bookings
    }

@router.post("/")
@router.post("")
def create_campaign(
    name: str = Query(...),
    description: Optional[str] = None,
    campaign_type: str = Query("call"),
    start_time: str = Query("09:00"),
    end_time: str = Query("18:00"),
    timezone: str = Query("America/New_York"),
    calls_per_minute: int = Query(5),
    max_attempts: int = Query(3),
    ai_script: Optional[str] = None,
    ai_persona_name: str = Query("Alex"),
    contact_ids: Optional[List[UUID]] = Query(None),
    assign_unassigned: bool = Query(False),
    assign_all: bool = Query(False),
    assign_all_with_email: bool = Query(False),
    lead_scope: Optional[str] = Query(None),
    source_files: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db)
):
    """Create a new campaign and associate leads using flexible filters"""
    from datetime import date, datetime, timedelta
    today_start = datetime.combine(date.today(), datetime.min.time())
    yesterday_start = datetime.combine(date.today() - timedelta(days=1), datetime.min.time())
    yesterday_end = datetime.combine(date.today() - timedelta(days=1), datetime.max.time())

    # Normalise campaign type
    valid_types = {"call", "email", "linkedin"}
    if campaign_type not in valid_types:
        campaign_type = "call"
    campaign = Campaign(
        name=name,
        description=description,
        status="draft",
        campaign_type=campaign_type,
        start_time=start_time,
        end_time=end_time,
        timezone=timezone,
        calls_per_minute=calls_per_minute,
        max_attempts=max_attempts,
        ai_script=ai_script,
        ai_persona_name=ai_persona_name
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    
    # Associate selected leads explicitly
    if contact_ids:
        db.query(Lead).filter(Lead.id.in_(contact_ids)).update({Lead.campaign_id: campaign.id}, synchronize_session=False)
        db.commit()

    # Scope-based assignment
    if lead_scope == "extracted_today":
        db.query(Lead).filter(Lead.is_active == True, Lead.created_at >= today_start).update({Lead.campaign_id: campaign.id}, synchronize_session=False)
        db.commit()
    elif lead_scope == "extracted_yesterday":
        db.query(Lead).filter(Lead.is_active == True, Lead.created_at >= yesterday_start, Lead.created_at <= yesterday_end).update({Lead.campaign_id: campaign.id}, synchronize_session=False)
        db.commit()
    elif lead_scope == "unsent_today":
        db.query(Lead).filter(Lead.is_active == True, Lead.email.isnot(None), Lead.email != "", Lead.created_at >= today_start, Lead.email_sent_at.is_(None)).update({Lead.campaign_id: campaign.id}, synchronize_session=False)
        db.commit()
    elif lead_scope == "unsent_yesterday":
        db.query(Lead).filter(Lead.is_active == True, Lead.email.isnot(None), Lead.email != "", Lead.created_at >= yesterday_start, Lead.created_at <= yesterday_end, Lead.email_sent_at.is_(None)).update({Lead.campaign_id: campaign.id}, synchronize_session=False)
        db.commit()
    elif lead_scope == "unsent_all":
        db.query(Lead).filter(Lead.is_active == True, Lead.email.isnot(None), Lead.email != "", Lead.email_sent_at.is_(None)).update({Lead.campaign_id: campaign.id}, synchronize_session=False)
        db.commit()
    # Associate ALL leads in the DB
    elif assign_all:
        db.query(Lead).filter(Lead.is_active == True).update({Lead.campaign_id: campaign.id}, synchronize_session=False)
        db.commit()
    # Associate ALL leads that have an email address
    elif assign_all_with_email:
        db.query(Lead).filter(
            Lead.is_active == True,
            Lead.email != None,
            Lead.email != ''
        ).update({Lead.campaign_id: campaign.id}, synchronize_session=False)
        db.commit()
    # Associate all unassigned leads if requested
    elif assign_unassigned:
        db.query(Lead).filter(Lead.campaign_id.is_(None), Lead.is_active == True).update({Lead.campaign_id: campaign.id}, synchronize_session=False)
        db.commit()

    # Associate unassigned leads matching selected source files
    if source_files and not assign_all and not assign_all_with_email and not lead_scope:
        db.query(Lead).filter(Lead.campaign_id.is_(None), Lead.is_active == True, Lead.source.in_(source_files)).update({Lead.campaign_id: campaign.id}, synchronize_session=False)
        db.commit()
        
    # Update total leads count
    campaign.total_leads = db.query(Lead).filter(Lead.campaign_id == campaign.id, Lead.is_active == True).count() # type: ignore
    db.commit()
        
    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "description": campaign.description,
        "status": campaign.status,
        "total_leads": campaign.total_leads,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None
    }

@router.patch("/{campaign_id}")
def update_campaign(
    campaign_id: UUID,
    name: Optional[str] = None,
    description: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    timezone: Optional[str] = None,
    calls_per_minute: Optional[int] = None,
    max_attempts: Optional[int] = None,
    ai_script: Optional[str] = None,
    ai_persona_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Update settings of an existing campaign (only allowed if draft or paused)"""
    campaign = db.query(Campaign).filter(text(f"campaigns.id = '{str(campaign_id)}'")).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    if campaign.status not in ["draft", "paused"]:
        raise HTTPException(status_code=400, detail="Campaign settings can only be updated in draft or paused states")
        
    if name is not None:
        campaign.name = name # type: ignore
    if description is not None:
        campaign.description = description # type: ignore
    if start_time is not None:
        campaign.start_time = start_time # type: ignore
    if end_time is not None:
        campaign.end_time = end_time # type: ignore
    if timezone is not None:
        campaign.timezone = timezone # type: ignore
    if calls_per_minute is not None:
        campaign.calls_per_minute = calls_per_minute # type: ignore
    if max_attempts is not None:
        campaign.max_attempts = max_attempts # type: ignore
    if ai_script is not None:
        campaign.ai_script = ai_script # type: ignore
    if ai_persona_name is not None:
        campaign.ai_persona_name = ai_persona_name # type: ignore
        
    db.commit()
    db.refresh(campaign)
    return campaign

@router.post("/{campaign_id}/start")
async def start_campaign(campaign_id: UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Start campaign dialing queue using Retell AI"""
    campaign = db.query(Campaign).filter(text(f"campaigns.id = '{str(campaign_id)}'")).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status == "active":
        raise HTTPException(status_code=400, detail="Campaign is already active")
        
    campaign.status = "active" # type: ignore
    campaign.started_at = datetime.now(timezone.utc) # type: ignore
    
    # Pull all pending leads assigned to this campaign
    leads = db.query(Lead).filter(
        text(f"leads.campaign_id = '{str(campaign_id)}'"),
        Lead.status == "pending",
        Lead.is_dnc == False,
        Lead.is_active == True
    ).all()
    
    # Update total_leads count
    total = db.query(Lead).filter(text(f"leads.campaign_id = '{str(campaign_id)}'"), Lead.is_active == True).count()
    campaign.total_leads = total # type: ignore
    db.commit()
    
    if not leads:
        return {"message": "Campaign started. No pending leads found to dial.", "leads_queued": 0, "status": "active"}
    
    from app.services.campaign_runner import is_within_allowed_run_windows, start_campaign_dialer
    
    # If currently within calling hours, trigger sequential calls immediately
    if is_within_allowed_run_windows():
        start_campaign_dialer(campaign_id)
        return {
            "message": f"Campaign started. Placed {len(leads)} leads into active dialer queue.",
            "leads_queued": len(leads),
            "status": "active_running"
        }
    else:
        return {
            "message": "Campaign activated. Dialer is currently on standby because the current time is outside allowed calling hours (8:00 PM - 10:00 PM, 12:00 AM - 1:00 AM, and 3:00 AM - 4:00 AM IST). Dialer will resume automatically during the next allowed window.",
            "leads_queued": len(leads),
            "status": "active_standby"
        }

@router.post("/{campaign_id}/pause")
def pause_campaign(campaign_id: UUID, db: Session = Depends(get_db)):
    """Pause dialer outreach"""
    campaign = db.query(Campaign).filter(text(f"campaigns.id = '{str(campaign_id)}'")).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.status = "paused" # type: ignore
    db.commit()
    return {"message": "Campaign paused successfully"}

@router.post("/{campaign_id}/resume")
async def resume_campaign(campaign_id: UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Resume dialer outreach"""
    campaign = db.query(Campaign).filter(text(f"campaigns.id = '{str(campaign_id)}'")).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    if campaign.status == "active":
        raise HTTPException(status_code=400, detail="Campaign is already active")
        
    campaign.status = "active" # type: ignore
    db.commit()
    
    # Pull remaining pending leads
    leads = db.query(Lead).filter(
        text(f"leads.campaign_id = '{str(campaign_id)}'"),
        Lead.status == "pending",
        Lead.is_dnc == False,
        Lead.is_active == True
    ).all()
    
    if not leads:
        return {"message": "Campaign resumed. No remaining pending leads to call.", "leads_queued": 0, "status": "active"}
        
    from app.services.campaign_runner import is_within_allowed_run_windows, start_campaign_dialer
    
    if is_within_allowed_run_windows():
        start_campaign_dialer(campaign_id)
        return {
            "message": f"Campaign resumed. Re-opened dialer queue for {len(leads)} leads.",
            "leads_queued": len(leads),
            "status": "active_running"
        }
    else:
        return {
            "message": "Campaign resumed. Dialer is currently on standby because the current time is outside allowed calling hours (8:00 PM - 10:00 PM, 12:00 AM - 1:00 AM, and 3:00 AM - 4:00 AM IST). Dialer will resume automatically during the next allowed window.",
            "leads_queued": len(leads),
            "status": "active_standby"
        }

@router.get("/{campaign_id}/leads")
def get_campaign_leads(
    campaign_id: UUID,
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """GET leads scoped specifically to this campaign"""
    query = db.query(Lead).filter(text(f"leads.campaign_id = '{str(campaign_id)}'"), Lead.is_active == True)
    if search:
        query = query.filter(Lead.full_name.ilike(f"%{search}%"))
    if status:
        query = query.filter(Lead.status == status)
        
    total = query.count()
    leads = query.offset((page - 1) * limit).limit(limit).all()
    return {"leads": leads, "total": total}

@router.get("/{campaign_id}/calls")
def get_campaign_calls(campaign_id: UUID, db: Session = Depends(get_db)):
    """GET call list for this campaign"""
    calls = db.query(Call).filter(text(f"calls.campaign_id = '{str(campaign_id)}'")).order_by(desc(Call.created_at)).all()
    return calls

@router.get("/{campaign_id}/appointments")
def get_campaign_appointments(campaign_id: UUID, db: Session = Depends(get_db)):
    """GET appointments booked from this campaign"""
    appts = db.query(Appointment).filter(text(f"appointments.campaign_id = '{str(campaign_id)}'")).order_by(desc(Appointment.created_at)).all()
    return appts

async def make_single_call_sqlalchemy(lead_id: UUID, campaign_id: UUID, retell_service: RetellService):
    """Executes call and creates database log records using SQLAlchemy Session"""
    from app.core.database import SessionLocal
    from app.utils.timezone import is_within_calling_hours
    
    db = SessionLocal()
    lead = None
    call_log = None
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        campaign = db.query(Campaign).filter(text(f"campaigns.id = '{str(campaign_id)}'")).first()
        if not lead or not campaign: return

        # Timezone calling hours compliance check
        if not is_within_calling_hours(str(lead.phone), str(lead.state)): # type: ignore
            lead.status = "failed" # type: ignore
            lead.internal_notes = "Call blocked: timezone compliance window guard." # type: ignore
            db.commit()
            return

        # Setup initiated Call log record
        call_log = Call(
            lead_id=lead.id,
            campaign_id=campaign.id,
            status="initiated",
            attempt_number=lead.call_attempts + 1 # type: ignore
        )
        db.add(call_log)
        
        lead.status = "calling" # type: ignore
        lead.call_attempts += 1 # type: ignore
        lead.total_calls += 1 # type: ignore
        lead.last_called_at = datetime.now(timezone.utc) # type: ignore
        
        # Send initial outreach Email in the background. SMS outreach is disabled here
        # and instead sent after the call completes, gated by a 15-second minimum talk duration.
        import asyncio
        from app.utils.automations import send_outreach_email
        
        if lead.email:
            asyncio.create_task(send_outreach_email(str(lead.email), lead.full_name or "there", lead.business_name, lead.business_type, lead_id=str(lead.id))) # type: ignore
            call_log.email_sent = True # type: ignore
            
        db.commit()

        # Trigger Retell Outbound Call API or Simulation
        from app.core.config import get_settings
        settings = get_settings()
        if settings.SIMULATE_CALLS:
            mock_call_id = f"sim_retell_{uuid4()}"
            call_log.retell_call_id = mock_call_id # type: ignore
            call_log.started_at = datetime.now(timezone.utc) # type: ignore
            db.commit()
            
            # Start simulation in background
            from app.services.call_simulator import simulate_call_lifecycle
            asyncio.create_task(simulate_call_lifecycle(str(lead_id), str(campaign_id), mock_call_id))
        else:
            retell_res = await retell_service.make_call(
                phone_number=str(lead.phone), # type: ignore
                campaign_id=str(campaign_id),
                contact_id=str(lead_id)
            )
            
            # Save real Call identifiers
            call_log.retell_call_id = retell_res.get("call_id") # type: ignore
            call_log.started_at = datetime.now(timezone.utc) # type: ignore
            db.commit()

    except Exception as e:
        logger.error("Error placing SQL call", lead_id=str(lead_id), error=str(e))
        try:
            if call_log:
                call_log.status = "failed" # type: ignore
                call_log.outcome = "error" # type: ignore
                call_log.transcript = f"Error initiating call: {str(e)}" # type: ignore
            if lead:
                lead.status = "failed" # type: ignore
                lead.internal_notes = f"Retell call initiation failed: {str(e)}" # type: ignore
            db.commit()
        except Exception as db_err:
            logger.error("Failed to save call error state", error=str(db_err))
    finally:
        db.close()

@router.post("/{campaign_id}/recampaign")
def recampaign_leads(
    campaign_id: UUID,
    reset_all: bool = Query(False, description="Reset all leads instead of only unpicked ones"),
    db: Session = Depends(get_db)
):
    """Bulk reset leads for a specific campaign back to pending"""
    campaign = db.query(Campaign).filter(text(f"campaigns.id = '{str(campaign_id)}'")).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    query = db.query(Lead).filter(
        text(f"leads.campaign_id = '{str(campaign_id)}'"),
        Lead.is_active == True
    )
    
    if not reset_all:
        # Only reset unpicked/failed/voicemail/no-answer ones
        query = query.filter(Lead.status.in_(["failed", "no_answer", "voicemail", "busy"]))
    else:
        # Reset all leads except those who successfully booked a meeting
        query = query.filter(Lead.status != "meeting_booked")
        
    leads_to_reset = query.all()
    
    count = 0
    for lead in leads_to_reset:
        lead.status = "pending" # type: ignore
        count += 1
        
    if campaign.status == "completed":
        campaign.status = "paused" # type: ignore
        
    db.commit()
    
    return {"message": f"Successfully added {count} leads back to the pending queue.", "requeued_count": count}