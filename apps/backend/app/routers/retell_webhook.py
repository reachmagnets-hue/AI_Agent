from fastapi import APIRouter, Request, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from datetime import datetime, date as datetime_date, timezone
import uuid
import re
import structlog

from app.core.database import get_db, SessionLocal
from app.models.call import Call
from app.models.lead import Lead
from app.models.appointment import Appointment
from app.services import email_service, sms_service, whatsapp_service, calcom_service
from app.core.websocket import websocket_manager

router = APIRouter(prefix="/api/retell", tags=["retell"])
logger = structlog.get_logger(__name__)

# ─── HELPER FUNCTIONS FOR DB OPERATIONS ───

def update_lead_status(lead_id: str, status: str):
    if not lead_id:
        return
    db = SessionLocal()
    try:
        lead_uuid = uuid.UUID(lead_id) if isinstance(lead_id, str) else lead_id
        lead = db.query(Lead).filter(Lead.id == lead_uuid).first()
        if lead:
            lead.status = status
            db.commit()
    except Exception as e:
        logger.error("Error updating lead status", lead_id=lead_id, error=str(e))
    finally:
        db.close()

def update_lead_from_analysis(lead_id: str, status: str, custom_data: dict = None, ai_summary: str = None):
    if not lead_id:
        return
    db = SessionLocal()
    try:
        lead_uuid = uuid.UUID(lead_id) if isinstance(lead_id, str) else lead_id
        lead = db.query(Lead).filter(Lead.id == lead_uuid).first()
        if lead:
            lead.status = status
            
            if custom_data:
                # Map lead score status to numeric score
                score_status = custom_data.get("lead_score_status", "Neutral")
                score_map = {
                    "Interested": 85,
                    "Neutral": 50,
                    "Not interested": 15
                }
                numeric_score = score_map.get(score_status, 50)
                if status == "meeting_booked":
                    numeric_score = 100
                elif status == "interested":
                    numeric_score = 90
                elif status == "not_interested":
                    numeric_score = 10
                
                lead.lead_score = numeric_score
                
                # Update decision maker status in notes
                dm_status = custom_data.get("is_decision_maker", "Uncertain")
                notes_addon = f"[AI Audit] Decision Maker: {dm_status} | Lead Score status: {score_status}"
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                formatted_note = f"\n[{timestamp}] {notes_addon}"
                if lead.internal_notes:
                    lead.internal_notes += formatted_note
                else:
                    lead.internal_notes = formatted_note.strip()
                    
            if ai_summary:
                lead.ai_summary = ai_summary
                
            db.commit()
    except Exception as e:
        logger.error("Error updating lead from analysis", lead_id=lead_id, error=str(e))
    finally:
        db.close()

def create_call_record(call_id: str, lead_id: str, call_data: dict):
    if not call_id or not lead_id:
        return
    db = SessionLocal()
    try:
        call = db.query(Call).filter(Call.retell_call_id == call_id).first()
        if not call:
            lead = db.query(Lead).filter(Lead.id == uuid.UUID(lead_id)).first()
            campaign_id = lead.campaign_id if lead else None
            call = Call(
                retell_call_id=call_id,
                lead_id=uuid.UUID(lead_id),
                campaign_id=campaign_id,
                status="initiated",
                from_number=call_data.get("from_number"),
                to_number=call_data.get("to_number"),
                started_at=datetime.now(timezone.utc)
            )
            db.add(call)
            db.commit()
    except Exception as e:
        logger.error("Error creating call record", call_id=call_id, error=str(e))
    finally:
        db.close()

def update_call_duration(call_id: str, duration: int):
    if not call_id:
        return
    db = SessionLocal()
    try:
        call = db.query(Call).filter(Call.retell_call_id == call_id).first()
        if call:
            call.duration_seconds = duration
            call.ended_at = datetime.now(timezone.utc)
            db.commit()
    except Exception as e:
        logger.error("Error updating call duration", call_id=call_id, error=str(e))
    finally:
        db.close()

def save_call_analysis(call_id: str, transcript: str, summary: str, outcome: str, analysis: dict, lead_id: str = None, campaign_id: str = None):
    if not call_id:
        return
    db = SessionLocal()
    try:
        call = db.query(Call).filter(Call.retell_call_id == call_id).first()
        if not call and lead_id:
            try:
                # Try to create call record on the fly if missed call_started event
                lead_uuid = uuid.UUID(lead_id) if isinstance(lead_id, str) else lead_id
                lead = db.query(Lead).filter(Lead.id == lead_uuid).first()
                
                camp_uuid = None
                if campaign_id:
                    camp_uuid = uuid.UUID(campaign_id) if isinstance(campaign_id, str) else campaign_id
                elif lead:
                    camp_uuid = lead.campaign_id

                call = Call(
                    retell_call_id=call_id,
                    lead_id=lead_uuid,
                    campaign_id=camp_uuid,
                    status="initiated",
                    started_at=datetime.now(timezone.utc)
                )
                db.add(call)
                db.commit()
            except Exception as e:
                logger.error("Error creating missing call record in save_call_analysis", call_id=call_id, error=str(e))
                
        # Re-fetch or use existing
        call = db.query(Call).filter(Call.retell_call_id == call_id).first()
        if call:
            call.transcript = transcript
            call.ai_summary = summary
            call.outcome = outcome
            call.status = "completed"
            call.recording_url = analysis.get("recording_url")
            call.objection_raised = analysis.get("objection_raised")
            
            if outcome == "meeting_booked":
                call.meeting_booked = True
                
            db.commit()
    except Exception as e:
        logger.error("Error saving call analysis", call_id=call_id, error=str(e))
    finally:
        db.close()


# ─── WEBHOOK ENDPOINT ───

@router.post("/webhook")
async def retell_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    data = await request.json()
    event = data.get("event")
    call_data = data.get("call", {})
    
    call_id = call_data.get("call_id")
    metadata = call_data.get("metadata", {})
    lead_id = metadata.get("lead_id") or metadata.get("contact_id")
    
    # ─── CALL STARTED ───
    if event == "call_started" and lead_id:
        update_lead_status(lead_id, "calling")
        create_call_record(call_id, lead_id, call_data)
    
    # ─── CALL ENDED ───
    elif event == "call_ended":
        duration = call_data.get("duration_ms", 0) // 1000
        update_call_duration(call_id, duration)
        if lead_id:
            update_lead_status(lead_id, "called")
    
    # ─── CALL ANALYZED (most important) ───  
    elif event == "call_analyzed":
        analysis = call_data.get("call_analysis", {})
        custom = analysis.get("custom_analysis_data", {})
        
        outcome = custom.get("outcome", "unknown")
        prospect_name = custom.get("prospect_name", "")
        business = custom.get("business_name", "")
        services = custom.get("services_interested", "")
        meeting_dt = custom.get("meeting_datetime", "")
        transcript = call_data.get("transcript", "")
        summary = analysis.get("call_summary", "")
        
        # Save transcript & analysis
        custom["recording_url"] = call_data.get("recording_url")
        save_call_analysis(
            call_id=call_id,
            transcript=transcript,
            summary=summary,
            outcome=outcome,
            analysis=custom,
            lead_id=lead_id,
            campaign_id=metadata.get("campaign_id")
        )
        
        # Update lead status based on outcome mapping
        status_map = {
            "meeting_booked": "meeting_booked",
            "interested_callback": "interested",
            "not_interested": "not_interested",
            "no_answer": "no_answer",
            "voicemail": "voicemail"
        }
        if lead_id:
            update_lead_from_analysis(lead_id, status_map.get(outcome, "called"), custom, summary)
            
        # Broadcast real-time call completed event to CRM
        background_tasks.add_task(
            websocket_manager.broadcast,
            {
                "event": "lead_status_updated",
                "lead_id": str(lead_id) if lead_id else None,
                "status": status_map.get(outcome, "called"),
                "outcome": outcome,
                "prospect_name": prospect_name,
                "business_name": business,
                "call_id": call_id
            }
        )
        
        # Fire post-call actions in background
        background_tasks.add_task(
            handle_post_call_actions,
            outcome=outcome,
            lead_id=lead_id,
            prospect_name=prospect_name,
            prospect_phone=call_data.get("to_number"),
            business=business,
            services=services,
            meeting_dt=meeting_dt,
            summary=summary
        )
    
    return {"status": "received"}


async def notify_rm_team(prospect_name: str, business: str, meeting_dt: str, services: str):
    """Notify the internal marketing team of scheduled discovery calls"""
    print(f"NOTIFY TEAM: New meeting booked with {prospect_name} ({business}) on {meeting_dt} for {services}")


async def handle_post_call_actions(
    outcome, lead_id, prospect_name, 
    prospect_phone, business, services,
    meeting_dt, summary
):
    """Fires SMS + Email + WhatsApp after call"""
    # Fetch phone from DB if missing
    if not prospect_phone and lead_id:
        db = SessionLocal()
        try:
            lead = db.query(Lead).filter(Lead.id == uuid.UUID(lead_id)).first()
            if lead:
                prospect_phone = lead.phone
                if not prospect_name:
                    prospect_name = lead.full_name or "there"
        finally:
            db.close()
            
    if not prospect_phone:
        print("Skipping post call actions: No phone number available.")
        return

    if outcome == "meeting_booked":
        msg = (f"Hi {prospect_name}! ✅ Your discovery call "
               f"with Reach Magnets is confirmed. "
               f"Check your email for the calendar invite. "
               f"Talk soon!")
        
        await sms_service.send(prospect_phone, msg)
        await whatsapp_service.send(prospect_phone, msg)
        await email_service.send_meeting_confirmation(
            prospect_name, prospect_phone, meeting_dt, services, lead_id
        )
        await notify_rm_team(prospect_name, business, meeting_dt, services)
    
    elif outcome == "interested_callback":
        msg = (f"Hi {prospect_name}! Sarah from Reach Magnets. "
               f"Great speaking with you! "
               f"I'll follow up as discussed. "
               f"Reply anytime if you have questions 😊")
        await sms_service.send(prospect_phone, msg)
    
    elif outcome == "no_answer":
        msg = (f"Hi! Sarah from Reach Magnets here. "
               f"We tried reaching you about growing your "
               f"business online. "
               f"Reply YES for a free marketing audit 📊")
        await sms_service.send(prospect_phone, msg)


# ─── MID-CALL BOOKING TOOL ───

@router.post("/book-appointment")
async def book_appointment_tool(request: Request):
    """
    Called by Retell AI MID-CALL when prospect agrees to meet.
    """
    data = await request.json()
    
    name = data.get("prospect_name")
    email = data.get("prospect_email")
    preferred_date = data.get("preferred_date", "")
    preferred_time = data.get("preferred_time", "")
    
    # Book on Cal.com
    booking = await calcom_service.book_slot(
        name=name,
        email=email,
        date=preferred_date,
        time=preferred_time
    )
    
    if booking["success"]:
        db = SessionLocal()
        try:
            lead = db.query(Lead).filter(Lead.email == email).first()
            if not lead and name:
                lead = db.query(Lead).filter(Lead.full_name.ilike(f"%{name}%")).first()
            
            call_obj = data.get("call", {})
            phone_num = call_obj.get("to_number") or ""
            if not lead and phone_num:
                lead = db.query(Lead).filter(Lead.phone == phone_num).first()
                
            if not lead:
                lead = Lead(
                    full_name=name or "Unknown Prospect",
                    email=email or "unknown@example.com",
                    phone=phone_num or "+1000000000",
                    status="meeting_booked",
                    source="inbound_booking"
                )
                db.add(lead)
                db.flush()
            
            lead_id = lead.id
            campaign_id = lead.campaign_id
            
            m_date = datetime_date.today()
            date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', preferred_date)
            if date_match:
                try:
                    m_date = datetime_date.fromisoformat(date_match.group(0))
                except Exception:
                    pass
                    
            appt = Appointment(
                lead_id=lead_id,
                campaign_id=campaign_id,
                title="Discovery Call - Reach Magnets",
                prospect_name=name,
                prospect_phone=lead.phone,
                prospect_email=email,
                prospect_business=lead.business_name or "",
                meeting_date=m_date,
                meeting_time=preferred_time,
                cal_meeting_link=booking["link"],
                status="confirmed"
            )
            db.add(appt)
            lead.status = "meeting_booked"
            db.commit()
        except Exception as e:
            print(f"Error saving appointment to DB: {e}")
        finally:
            db.close()
            
        return {
            "status": "booked",
            "message": f"Booked for {booking['date']} at {booking['time']}",
            "meeting_link": booking["link"]
        }
    else:
        return {
            "status": "failed",
            "message": "No slots available at that time. Ask for alternative."
        }
