from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func
from typing import List, Optional
from datetime import datetime, date, timezone
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
    
    # Pre-calculate or dynamically aggregate totals
    data = []
    for c in campaigns:
        total_leads = db.query(Lead).filter(Lead.campaign_id == c.id).count()
        total_called = db.query(Call).filter(Call.campaign_id == c.id).count()
        total_answered = db.query(Call).filter(Call.campaign_id == c.id, Call.status == "completed").count()
        total_booked = db.query(Appointment).filter(Appointment.campaign_id == c.id).count()
        
        # New Detailed Stats
        total_pending = db.query(Lead).filter(Lead.campaign_id == c.id, Lead.status == "pending", Lead.is_active == True).count()
        total_unpicked = db.query(Lead).filter(Lead.campaign_id == c.id, Lead.status.in_(["failed", "no_answer", "voicemail", "busy"]), Lead.is_active == True).count()
        
        data.append({
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "status": c.status,
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
            "created_at": c.created_at,
            "started_at": c.started_at,
            "completed_at": c.completed_at
        })
    return data

@router.get("/{campaign_id}")
def get_campaign(campaign_id: UUID, db: Session = Depends(get_db)):
    """Retrieve full campaign overview panel details with conversion funnel stats"""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    total_leads = db.query(Lead).filter(Lead.campaign_id == campaign_id).count()
    called = db.query(Call).filter(Call.campaign_id == campaign_id).count()
    answered = db.query(Call).filter(Call.campaign_id == campaign_id, Call.status == "completed").count()
    interested = db.query(Call).filter(Call.campaign_id == campaign_id, Call.outcome == "interested").count()
    booked = db.query(Appointment).filter(Appointment.campaign_id == campaign_id).count()
    no_answer = db.query(Call).filter(Call.campaign_id == campaign_id, Call.status == "no_answer").count()
    
    # Cost estimation
    total_duration_sec = db.query(func.sum(Call.duration_seconds)).filter(Call.campaign_id == campaign_id).scalar() or 0
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
        "estimated_cost": round(estimated_cost, 2)
    }

    # Fetch last 10 calls
    recent_calls = db.query(Call).filter(Call.campaign_id == campaign_id).order_by(desc(Call.created_at)).limit(10).all()
    # Fetch last 5 appointments
    recent_bookings = db.query(Appointment).filter(Appointment.campaign_id == campaign_id).order_by(desc(Appointment.created_at)).limit(5).all()

    return {
        "campaign": campaign,
        "stats": stats,
        "recent_calls": recent_calls,
        "recent_bookings": recent_bookings
    }

@router.post("/")
def create_campaign(
    name: str = Query(...),
    description: Optional[str] = None,
    start_time: str = Query("09:00"),
    end_time: str = Query("18:00"),
    timezone: str = Query("America/New_York"),
    calls_per_minute: int = Query(5),
    max_attempts: int = Query(3),
    ai_script: Optional[str] = None,
    ai_persona_name: str = Query("Alex"),
    contact_ids: Optional[List[UUID]] = Query(None),
    assign_unassigned: bool = Query(False),
    source_files: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db)
):
    """Create a new campaign and associate leads"""
    campaign = Campaign(
        name=name,
        description=description,
        status="draft",
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
        
    # Associate all unassigned leads if requested
    if assign_unassigned:
        db.query(Lead).filter(Lead.campaign_id.is_(None), Lead.is_active == True).update({Lead.campaign_id: campaign.id}, synchronize_session=False)
        db.commit()

    # Associate unassigned leads matching selected source files
    if source_files:
        db.query(Lead).filter(Lead.campaign_id.is_(None), Lead.is_active == True, Lead.source.in_(source_files)).update({Lead.campaign_id: campaign.id}, synchronize_session=False)
        db.commit()
        
    # Update total leads count
    campaign.total_leads = db.query(Lead).filter(Lead.campaign_id == campaign.id, Lead.is_active == True).count()
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
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    if campaign.status not in ["draft", "paused"]:
        raise HTTPException(status_code=400, detail="Campaign settings can only be updated in draft or paused states")
        
    if name is not None:
        campaign.name = name
    if description is not None:
        campaign.description = description
    if start_time is not None:
        campaign.start_time = start_time
    if end_time is not None:
        campaign.end_time = end_time
    if timezone is not None:
        campaign.timezone = timezone
    if calls_per_minute is not None:
        campaign.calls_per_minute = calls_per_minute
    if max_attempts is not None:
        campaign.max_attempts = max_attempts
    if ai_script is not None:
        campaign.ai_script = ai_script
    if ai_persona_name is not None:
        campaign.ai_persona_name = ai_persona_name
        
    db.commit()
    db.refresh(campaign)
    return campaign

@router.post("/{campaign_id}/start")
async def start_campaign(campaign_id: UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Start campaign dialing queue using Retell AI"""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status == "active":
        raise HTTPException(status_code=400, detail="Campaign is already active")
        
    campaign.status = "active"
    campaign.started_at = datetime.now(timezone.utc)
    
    # Pull all pending leads assigned to this campaign
    leads = db.query(Lead).filter(
        Lead.campaign_id == campaign_id,
        Lead.status == "pending",
        Lead.is_dnc == False,
        Lead.is_active == True
    ).all()
    
    # Update total_leads count
    total = db.query(Lead).filter(Lead.campaign_id == campaign_id, Lead.is_active == True).count()
    campaign.total_leads = total
    db.commit()
    
    if not leads:
        return {"message": "Campaign started. No pending leads found to dial.", "leads_queued": 0}
    
    retell_service = RetellService()
    lead_ids = [lead.id for lead in leads]
    
    # Dispatch each call as a proper async background task
    async def run_all_calls():
        import asyncio
        from app.core.database import SessionLocal
        for lid in lead_ids:
            # Resiliency Check: Verify if campaign was paused or stopped
            db_session = SessionLocal()
            try:
                camp = db_session.query(Campaign).filter(Campaign.id == campaign_id).first()
                if not camp or camp.status != "active":
                    logger.info("Campaign is no longer active. Exiting background dialer loop.", campaign_id=str(campaign_id))
                    break
            except Exception as e:
                logger.error("Error checking campaign status in dialer loop", error=str(e))
            finally:
                db_session.close()

            await make_single_call_sqlalchemy(lid, campaign_id, retell_service)
            await asyncio.sleep(1.5)  # ~40 calls/minute rate limit buffer
    
    background_tasks.add_task(run_all_calls)
    
    return {"message": f"Campaign started. Queued {len(leads)} leads for calling.", "leads_queued": len(leads)}

@router.post("/{campaign_id}/pause")
def pause_campaign(campaign_id: UUID, db: Session = Depends(get_db)):
    """Pause dialer outreach"""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.status = "paused"
    db.commit()
    return {"message": "Campaign paused successfully"}

@router.post("/{campaign_id}/resume")
def resume_campaign(campaign_id: UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Resume dialer outreach"""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    campaign.status = "active"
    db.commit()
    
    # Pull remaining pending leads
    leads = db.query(Lead).filter(Lead.campaign_id == campaign_id, Lead.status == "pending", Lead.is_dnc == False).all()
    retell_service = RetellService()
    
    for lead in leads:
        background_tasks.add_task(
            make_single_call_sqlalchemy,
            lead.id,
            campaign_id,
            retell_service
        )
        
    return {"message": f"Campaign resumed, initiated calls to {len(leads)} leads."}

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
    query = db.query(Lead).filter(Lead.campaign_id == campaign_id, Lead.is_active == True)
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
    calls = db.query(Call).filter(Call.campaign_id == campaign_id).order_by(desc(Call.created_at)).all()
    return calls

@router.get("/{campaign_id}/appointments")
def get_campaign_appointments(campaign_id: UUID, db: Session = Depends(get_db)):
    """GET appointments booked from this campaign"""
    appts = db.query(Appointment).filter(Appointment.campaign_id == campaign_id).order_by(desc(Appointment.created_at)).all()
    return appts

async def make_single_call_sqlalchemy(lead_id: UUID, campaign_id: UUID, retell_service: RetellService):
    """Executes call and creates database log records using SQLAlchemy Session"""
    from app.core.database import SessionLocal
    from app.utils.timezone import is_within_calling_hours
    
    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not lead or not campaign: return

        # Timezone calling hours compliance check
        if not is_within_calling_hours(lead.phone, lead.state):
            lead.status = "failed"
            lead.internal_notes = "Call blocked: timezone compliance window guard."
            db.commit()
            return

        # Setup initiated Call log record
        call_log = Call(
            lead_id=lead.id,
            campaign_id=campaign.id,
            status="initiated",
            attempt_number=lead.call_attempts + 1
        )
        db.add(call_log)
        
        lead.status = "calling"
        lead.call_attempts += 1
        lead.total_calls += 1
        lead.last_called_at = datetime.now(timezone.utc)
        
        # Send initial outreach SMS & Email in the background
        import asyncio
        from app.utils.automations import send_outreach_sms, send_outreach_email
        
        if lead.phone:
            asyncio.create_task(send_outreach_sms(lead.phone, lead.full_name or "there", lead.business_name))
            call_log.sms_sent = True
        if lead.email:
            asyncio.create_task(send_outreach_email(lead.email, lead.full_name or "there", lead.business_name, lead.business_type))
            call_log.email_sent = True
            
        db.commit()

        # Trigger Retell Outbound Call API
        retell_res = await retell_service.make_call(
            phone_number=lead.phone,
            campaign_id=str(campaign_id),
            contact_id=str(lead_id)
        )
        
        # Save real Call identifiers
        call_log.retell_call_id = retell_res.get("call_id")
        call_log.started_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        logger.error("Error placing SQL call", lead_id=str(lead_id), error=str(e))
        try:
            if 'call_log' in locals() and call_log:
                call_log.status = "failed"
                call_log.outcome = "error"
                call_log.transcript = f"Error initiating call: {str(e)}"
            if 'lead' in locals() and lead:
                lead.status = "failed"
                lead.internal_notes = f"Retell call initiation failed: {str(e)}"
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
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    query = db.query(Lead).filter(
        Lead.campaign_id == campaign_id,
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
        lead.status = "pending"
        count += 1
        
    if campaign.status == "completed":
        campaign.status = "paused"
        
    db.commit()
    
    return {"message": f"Successfully added {count} leads back to the pending queue.", "requeued_count": count}