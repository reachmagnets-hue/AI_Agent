from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Dict, Any
from datetime import datetime, date
import structlog
from uuid import UUID

from app.core.database import get_db, SessionLocal
from app.models.lead import Lead
from app.models.call import Call
from app.models.appointment import Appointment
from app.models.campaign import Campaign
from app.core.websocket import websocket_manager

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@router.post("/vapi")
async def handle_vapi_webhook(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    """
    Handle webhooks from Vapi.ai
    It processes different event types and updates the database using SQLAlchemy.
    """
    try:
        call_data = payload.get("call", {})
        event_type = payload.get("type", "unknown")
        call_id = call_data.get("id")
        
        logger.info("Received Vapi webhook", event_type=event_type, call_id=call_id)
        
        db = SessionLocal()
        try:
            if event_type == "call.updated":
                await process_vapi_call_update(db, call_data)
            elif event_type == "call.status.completed":
                await process_vapi_call_completed(db, call_data, background_tasks)
            elif event_type == "call.hang_up":
                await process_vapi_call_ended(db, call_data)
        finally:
            db.close()
            
        return {"message": "Webhook processed successfully"}
    except Exception as e:
        logger.error("Vapi webhook processing error", error=str(e), exc_info=True)
        return {"message": "Error processed", "detail": str(e)}

@router.post("/retell")
async def handle_retell_webhook(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    """
    Handle webhooks from Retell AI.
    Processes call progress and updates analytics, triggers notifications for appointments.
    """
    event = payload.get("event")
    call_data = payload.get("call", {})
    call_id = call_data.get("call_id")
    
    logger.info("Received Retell webhook", webhook_event=event, call_id=call_id)
    
    db = SessionLocal()
    try:
        metadata = call_data.get("metadata", {})
        campaign_id_str = metadata.get("campaign_id")
        contact_id_str = metadata.get("contact_id")
        
        campaign_id = UUID(campaign_id_str) if campaign_id_str else None
        lead_id = UUID(contact_id_str) if contact_id_str else None

        if event == "call_started":
            # Check if record exists
            call_record = db.query(Call).filter(Call.retell_call_id == call_id).first()
            if not call_record and lead_id:
                new_call = Call(
                    lead_id=lead_id,
                    campaign_id=campaign_id,
                    retell_call_id=call_id,
                    status="initiated",
                    started_at=datetime.utcnow()
                )
                db.add(new_call)
                db.commit()
                
        elif event in ["call_ended", "call_analyzed"]:
            transcript = call_data.get("transcript", "")
            recording_url = call_data.get("recording_url", "")
            duration_seconds = int(call_data.get("duration_ms", 0) / 1000)
            
            # Retell call status mapping
            disconnect_reason = call_data.get("disconnection_reason", "agent_hangup")
            if disconnect_reason in ["no_answer", "dial_no_answer"]:
                internal_status = "no_answer"
            elif disconnect_reason in ["dial_failed", "error"]:
                internal_status = "failed"
            else:
                internal_status = "completed"
                
            # Retell call analysis data
            analysis = call_data.get("call_analysis", {})
            custom_analysis = analysis.get("custom_analysis_data", {}) or {}
            ai_summary = analysis.get("call_summary", "") or analysis.get("summary", "")
                
            call_record = db.query(Call).filter(Call.retell_call_id == call_id).first()
            
            call_fields = {
                "status": internal_status,
                "duration_seconds": duration_seconds,
                "transcript": transcript,
                "recording_url": recording_url,
                "ai_summary": ai_summary,
                "objection_raised": custom_analysis.get("objection_raised"),
                "ended_at": datetime.utcnow()
            }
            
            if call_record:
                for key, val in call_fields.items():
                    setattr(call_record, key, val)
            else:
                if lead_id:
                    call_record = Call(
                        lead_id=lead_id,
                        campaign_id=campaign_id,
                        retell_call_id=call_id,
                        **call_fields
                    )
                    db.add(call_record)
            db.commit()
            
            # Analyze intent from transcript keywords
            contact_status = analyze_transcript_intent(transcript)
            
            appointment_booked = False
            appointment_details = "Digital Marketing Discovery Audit - Reach Magnets"
            
            # Check if AI confirmed a meeting was booked
            scheduled_flag = (
                custom_analysis.get("scheduled") or
                custom_analysis.get("meeting_booked") or
                custom_analysis.get("appointment_booked")
            )
            transcript_lower = transcript.lower()
            booking_keywords_in_transcript = any(kw in transcript_lower for kw in [
                "meeting booked", "appointment confirmed", "scheduled a call",
                "i'll book", "let's schedule", "block the time", "confirm the slot"
            ])
            if scheduled_flag or booking_keywords_in_transcript:
                appointment_booked = True
                contact_status = "meeting_booked"
                appointment_details = (
                    custom_analysis.get("appointment_time") or
                    custom_analysis.get("meeting_time") or
                    "Discovery Audit Consultation - Reach Magnets"
                )
            
            # Update Lead profile from AI-extracted data
            if lead_id:
                lead = db.query(Lead).filter(Lead.id == lead_id).first()
                if lead:
                    lead.status = contact_status
                    lead.last_called_at = datetime.utcnow()
                    lead.total_calls = (lead.total_calls or 0) + 1
                    
                    # Save AI-extracted call summary to lead
                    if ai_summary and not lead.ai_summary:
                        lead.ai_summary = ai_summary

                    # Update Lead scoring status and decision maker info
                    score_status = custom_analysis.get("lead_score_status", "Neutral")
                    score_map = {
                        "Interested": 85,
                        "Neutral": 50,
                        "Not interested": 15
                    }
                    numeric_score = score_map.get(score_status, 50)
                    if contact_status == "meeting_booked":
                        numeric_score = 100
                    elif contact_status == "interested":
                        numeric_score = 90
                    elif contact_status == "not_interested":
                        numeric_score = 10
                    
                    lead.lead_score = numeric_score
                    
                    dm_status = custom_analysis.get("is_decision_maker", "Uncertain")
                    notes_addon = f"[AI Audit] Decision Maker: {dm_status} | Lead Score status: {score_status}"
                    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    formatted_note = f"\n[{timestamp}] {notes_addon}"
                    if lead.internal_notes:
                        lead.internal_notes += formatted_note
                    else:
                        lead.internal_notes = formatted_note.strip()
                    
                    # Dynamically capture contact details collected by Alex during the call
                    extracted_name = (
                        custom_analysis.get("client_name") or
                        custom_analysis.get("name") or
                        custom_analysis.get("prospect_name")
                    )
                    extracted_email = (
                        custom_analysis.get("client_email") or
                        custom_analysis.get("email") or
                        custom_analysis.get("prospect_email")
                    )
                    extracted_business = (
                        custom_analysis.get("business_name") or
                        custom_analysis.get("business") or
                        custom_analysis.get("company")
                    )
                    
                    if extracted_name and not lead.full_name:
                        lead.full_name = extracted_name
                    if extracted_email and not lead.email:
                        lead.email = extracted_email
                    if extracted_business and not lead.business_name:
                        lead.business_name = extracted_business

                    if appointment_booked:
                        # Extract meeting time from AI analysis or fallback
                        raw_time = (
                            custom_analysis.get("appointment_time") or
                            custom_analysis.get("meeting_time") or
                            custom_analysis.get("booked_time") or
                            "14:00"
                        )
                        raw_date_str = (
                            custom_analysis.get("appointment_date") or
                            custom_analysis.get("meeting_date")
                        )
                        try:
                            meeting_date = datetime.strptime(raw_date_str, "%Y-%m-%d").date() if raw_date_str else date.today()
                        except Exception:
                            meeting_date = date.today()
                            
                        appt = Appointment(
                            lead_id=lead.id,
                            call_id=call_record.id if call_record else None,
                            campaign_id=campaign_id,
                            prospect_name=lead.full_name or "Prospect",
                            prospect_phone=lead.phone,
                            prospect_email=lead.email,
                            prospect_business=lead.business_name,
                            meeting_date=meeting_date,
                            meeting_time=raw_time[:5] if len(raw_time) >= 5 else "14:00",
                            title="Discovery Call - Reach Magnets Marketing Audit",
                            discussion_summary=ai_summary or analysis.get("summary", ""),
                            services_interested=str(custom_analysis.get("services_interested", "")),
                            prospect_pain_points=str(custom_analysis.get("pain_points", ""))
                        )
                        db.add(appt)
                        if call_record:
                            call_record.meeting_booked = True
                        
                    db.commit()
                    
                    # Trigger SMS / Email / WhatsApp notifications
                    if appointment_booked or contact_status == "interested":
                        from app.utils.automations import send_appointment_email, send_appointment_sms, send_whatsapp_message
                        
                        contact_name = lead.full_name or "Valued Client"
                        contact_phone = lead.phone
                        contact_email = lead.email or "audit@reachmagnets.com"
                        
                        background_tasks.add_task(
                            send_appointment_sms,
                            contact_phone,
                            contact_name,
                            appointment_details
                        )
                        background_tasks.add_task(
                            send_appointment_email,
                            contact_email,
                            contact_name,
                            appointment_details
                        )
                        whatsapp_msg = (
                            f"Hi {contact_name}, your Discovery Session with Reach Magnets is confirmed! "
                            f"{appointment_details}. "
                            "Reply to this chat if you have any questions before the call!"
                        )
                        background_tasks.add_task(
                            send_whatsapp_message,
                            contact_phone,
                            contact_name,
                            whatsapp_msg
                        )
                        if call_record:
                            call_record.sms_sent = True
                            call_record.email_sent = True
                            db.commit()

            # Broadcast real-time call completed event to CRM
            background_tasks.add_task(
                websocket_manager.broadcast,
                {
                    "event": "lead_status_updated",
                    "lead_id": str(lead_id) if lead_id else None,
                    "status": contact_status,
                    "outcome": custom_analysis.get("outcome", "unknown"),
                    "prospect_name": lead.full_name if lead else "Prospect",
                    "business_name": lead.business_name if lead else "Business",
                    "call_id": call_id
                }
            )

            # Update campaign stats
            if campaign_id:
                await increment_campaign_stats_db(db, campaign_id, internal_status)
                
    except Exception as e:
        logger.error("Retell webhook processing error", error=str(e), exc_info=True)
    finally:
        db.close()
        
    return {"message": "Retell webhook handled successfully"}

async def process_vapi_call_update(db: Session, call_data: Dict[str, Any]):
    call_id = call_data.get("id")
    status = call_data.get("status")
    metadata = call_data.get("metadata", {})
    
    call_record = db.query(Call).filter(Call.twilio_call_sid == call_id).first()
    
    if not call_record:
        campaign_id_str = metadata.get("campaign_id")
        contact_id_str = metadata.get("contact_id")
        
        lead_id = UUID(contact_id_str) if contact_id_str else None
        campaign_id = UUID(campaign_id_str) if campaign_id_str else None
        
        if lead_id:
            new_call = Call(
                lead_id=lead_id,
                campaign_id=campaign_id,
                twilio_call_sid=call_id,
                status=get_vapi_internal_status(status),
                started_at=datetime.utcnow()
            )
            db.add(new_call)
            db.commit()
    else:
        call_record.status = get_vapi_internal_status(status)
        if status == "answered" and call_record.campaign_id:
            await increment_campaign_stats_db(db, call_record.campaign_id, "answered")
        db.commit()

async def process_vapi_call_completed(db: Session, call_data: Dict[str, Any], background_tasks: BackgroundTasks):
    call_id = call_data.get("id")
    call_record = db.query(Call).filter(Call.twilio_call_sid == call_id).first()
    
    if call_record:
        call_record.status = "completed"
        call_record.duration_seconds = call_data.get("duration", 0)
        call_record.transcript = call_data.get("transcript", "")
        call_record.recording_url = call_data.get("recordingUrl")
        call_record.ended_at = datetime.utcnow()
        
        contact_status = analyze_transcript_intent(call_data.get("transcript", ""))
        
        lead = db.query(Lead).filter(Lead.id == call_record.lead_id).first()
        if lead:
            lead.status = contact_status
            
        db.commit()
        
        if call_record.campaign_id:
            await increment_campaign_stats_db(db, call_record.campaign_id, "completed")

async def process_vapi_call_ended(db: Session, call_data: Dict[str, Any]):
    call_id = call_data.get("id")
    status = call_data.get("status")
    
    call_record = db.query(Call).filter(Call.twilio_call_sid == call_id).first()
    if call_record:
        vapi_status = get_vapi_internal_status(status)
        call_record.status = vapi_status
        call_record.ended_at = datetime.utcnow()
        
        lead = db.query(Lead).filter(Lead.id == call_record.lead_id).first()
        if lead:
            lead.status = "failed" if vapi_status == "failed" else "called"
            
        db.commit()
        
        if call_record.campaign_id:
            await increment_campaign_stats_db(db, call_record.campaign_id, vapi_status)

def get_vapi_internal_status(vapi_status: str) -> str:
    status_mapping = {
        "queued": "initiated",
        "waiting-client": "ringing",
        "in-progress": "answered",
        "completed": "completed",
        "ended": "completed",
        "failed": "failed",
        "no-answer": "no_answer",
        "busy": "no_answer",
        "cancelled": "failed"
    }
    return status_mapping.get(vapi_status, "failed")

def analyze_transcript_intent(transcript: str) -> str:
    import re
    if not transcript:
        return "called"
    lower_t = transcript.lower()
    
    # Check for meeting booked first (highest confidence)
    booking_kws = ["meeting booked", "appointment confirmed", "scheduled", "slot confirmed", "block the time", "confirm the slot", "i'll send a calendar"]
    if any(kw in lower_t for kw in booking_kws):
        return "meeting_booked"
    
    interest_keywords = [
        "interested", "yes please", "sounds good", "tell me more", "pricing",
        "demo", "consultation", "want to know", "how much", "can you send",
        "what services", "grow my", "help my business", "more clients"
    ]
    no_interest_keywords = [
        "not interested", "no thank you", "no thanks", "wrong number",
        "stop calling", "remove me", "don't call", "busy right now",
        "nahi chahiye", "mujhe nahi chahiye"
    ]
    
    interest_score = sum(1 for kw in interest_keywords if kw in lower_t)
    no_interest_score = sum(1 for kw in no_interest_keywords if kw in lower_t)
    
    if interest_score >= 2 and no_interest_score == 0:
        return "interested"
    elif no_interest_score >= 1:
        return "not_interested"
    else:
        return "called"

async def increment_campaign_stats_db(db: Session, campaign_id: UUID, status_type: str):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if campaign:
        campaign.total_called += 1
        if status_type in ["completed", "answered"]:
            campaign.total_answered += 1
        if status_type == "meeting_booked":
            campaign.total_booked += 1
        db.commit()

from typing import Union, List

@router.post("/brevo")
async def handle_brevo_webhook(payload: Union[Dict[str, Any], List[Dict[str, Any]]], db: Session = Depends(get_db)):
    """
    Handle webhook events from Brevo for email status tracking (delivered, opened, clicked, bounced, blocked)
    """
    events = payload if isinstance(payload, list) else [payload]
    results = []
    
    for event_data in events:
        event = event_data.get("event")
        email = event_data.get("email")
        msg_id = event_data.get("message-id") or event_data.get("message_id")
        
        if not msg_id:
            continue
            
        # Search for lead by email_msg_id
        lead = db.query(Lead).filter(Lead.email_msg_id == msg_id).first()
        if not lead and email:
            # Fallback to email search
            lead = db.query(Lead).filter(Lead.email == email, Lead.is_active == True).order_by(Lead.updated_at.desc()).first()
            
        if lead:
            now_utc = datetime.utcnow()
            if event in ["request", "sent"]:
                lead.email_status = "sent"
            elif event == "delivered":
                lead.email_status = "delivered"
                lead.email_delivered_at = now_utc
            elif event in ["opened", "unique_opened"]:
                lead.email_status = "opened"
                if not lead.email_opened_at:
                    lead.email_opened_at = now_utc
            elif event == "click":
                lead.email_status = "clicked"
                if not lead.email_clicked_at:
                    lead.email_clicked_at = now_utc
            elif event in ["bounces", "bounce", "hardBounce", "softBounce"]:
                lead.email_status = "bounced"
                lead.email_bounced_at = now_utc
            elif event in ["blocked", "spam", "unsubscribed"]:
                lead.email_status = "blocked"
                lead.email_blocked_at = now_utc
                
            lead.updated_at = now_utc
            db.commit()
            results.append({"lead_id": str(lead.id), "status": lead.email_status})
            
    return {"status": "success", "updates": results}

@router.post("/health")
async def webhook_health():
    return {"status": "healthy", "service": "webhooks"}