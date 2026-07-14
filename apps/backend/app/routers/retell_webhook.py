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
from app.services import email_service, sms_service, whatsapp_service, gmeet_service
from app.core.websocket import websocket_manager

router = APIRouter(prefix="/api/retell", tags=["retell"])
logger = structlog.get_logger(__name__)

# ─── HELPER FUNCTIONS FOR DB OPERATIONS ───

def clean_email_address(email: str) -> str | None:
    if not email:
        return None
    email = email.strip().lower()
    
    # Check for placeholder patterns
    placeholders = [
        "example@gmail", "example@gmail.com", "test@gmail.com", "contact@gmail.com",
        "contact@gmails.com", "placeholder@gmail.com", "unknown@example.com"
    ]
    if email in placeholders or "example" in email or "placeholder" in email:
        return None
        
    # Correct common typos in domains
    import re
    email = re.sub(r'@gmilas\.com$', '@gmail.com', email)
    email = re.sub(r'@gmil\.com$', '@gmail.com', email)
    email = re.sub(r'@gmaill\.com$', '@gmail.com', email)
    email = re.sub(r'@gamil\.com$', '@gmail.com', email)
    email = re.sub(r'@gmile\.com$', '@gmail.com', email)
    email = re.sub(r'@gmails\.com$', '@gmail.com', email)
    
    # Quick regex to validate structure
    if not re.match(r'[^@]+@[^@]+\.[^@]+', email):
        return None
        
    return email

def update_lead_status(lead_id: str, status: str):
    if not lead_id:
        return
    db = SessionLocal()
    try:
        lead_uuid = uuid.UUID(lead_id) if isinstance(lead_id, str) else lead_id
        lead = db.query(Lead).filter(Lead.id == lead_uuid).first()
        if lead:
            lead.status = status # type: ignore
            db.commit()
    except Exception as e:
        logger.error("Error updating lead status", lead_id=lead_id, error=str(e))
    finally:
        db.close()

def update_lead_from_analysis(lead_id: str, status: str, custom_data: dict | None = None, ai_summary: str | None = None):
    if not lead_id:
        return
    db = SessionLocal()
    try:
        lead_uuid = uuid.UUID(lead_id) if isinstance(lead_id, str) else lead_id
        lead = db.query(Lead).filter(Lead.id == lead_uuid).first()
        if lead:
            lead.status = status # type: ignore
            
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
                
                lead.lead_score = numeric_score # type: ignore
                
                # Extract and update prospect fields from custom_data
                p_name = custom_data.get("prospect_name")
                b_name = custom_data.get("business_name")
                p_email = custom_data.get("prospect_email")
                p_phone = custom_data.get("prospect_phone")
                z_code = custom_data.get("zip_code")
                
                if p_name and (not lead.full_name or lead.full_name == "Prospect"):
                    lead.full_name = p_name.strip()  # type: ignore
                if b_name and not lead.business_name:
                    lead.business_name = b_name.strip()  # type: ignore
                if p_email:
                    cleaned_email = clean_email_address(p_email)
                    if cleaned_email and (not lead.email or lead.email == "unknown@example.com" or "example" in lead.email):
                        lead.email = cleaned_email  # type: ignore
                if p_phone and not lead.phone:
                    lead.phone = p_phone.strip()  # type: ignore
                if z_code:
                    lead.zip_code = z_code.strip()  # type: ignore
                
                # Update decision maker status in notes
                dm_status = custom_data.get("is_decision_maker", "Uncertain")
                notes_addon = f"[AI Audit] Decision Maker: {dm_status} | Lead Score status: {score_status}"
                if z_code:
                    notes_addon += f" | Zip code collected: {z_code}"
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                formatted_note = f"\n[{timestamp}] {notes_addon}"
                if lead.internal_notes:
                    lead.internal_notes = (lead.internal_notes or "") + formatted_note # type: ignore
                else:
                    lead.internal_notes = formatted_note.strip() # type: ignore
                    
            if status == "meeting_booked":
                # Create appointment fallback if it does not exist
                from app.models.appointment import Appointment
                from datetime import date as datetime_date, timedelta
                import re
                
                appt = db.query(Appointment).filter(Appointment.lead_id == lead_uuid).first()
                if not appt:
                    meeting_dt_str = custom_data.get("meeting_datetime", "") if custom_data else ""
                    m_date = datetime_date.today() + timedelta(days=3)
                    preferred_time = "5:00 PM"
                    
                    if meeting_dt_str:
                        date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', meeting_dt_str)
                        if date_match:
                            try:
                                m_date = datetime_date.fromisoformat(date_match.group(0))
                            except Exception:
                                pass
                        else:
                            lower_dt = meeting_dt_str.lower()
                            weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                            for i, w in enumerate(weekdays):
                                if w in lower_dt:
                                    today_wd = datetime_date.today().weekday()
                                    days_ahead = i - today_wd
                                    if days_ahead <= 0:
                                        days_ahead += 7
                                    m_date = datetime_date.today() + timedelta(days=days_ahead)
                                    break
                        
                        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)?', meeting_dt_str)
                        if time_match:
                            hr = time_match.group(1)
                            mn = time_match.group(2) or "00"
                            ampm = time_match.group(3) or "PM"
                            preferred_time = f"{hr}:{mn} {ampm.upper()}"
                    
                    appt = Appointment(
                        lead_id=lead_uuid,
                        campaign_id=lead.campaign_id,
                        title="Discovery Call - Reach Magnets",
                        prospect_name=lead.full_name or "Unknown Prospect",
                        prospect_phone=lead.phone,
                        prospect_email=lead.email or "unknown@example.com",
                        prospect_business=lead.business_name or "",
                        meeting_date=m_date,
                        meeting_time=preferred_time,
                        discussion_summary=ai_summary or "Booked via outbound call fallback",
                        status="confirmed"
                    )
                    db.add(appt)

            if ai_summary:
                lead.ai_summary = ai_summary # type: ignore
                
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
            call.duration_seconds = duration # type: ignore
            call.ended_at = datetime.now(timezone.utc) # type: ignore
            db.commit()
    except Exception as e:
        logger.error("Error updating call duration", call_id=call_id, error=str(e))
    finally:
        db.close()

def save_call_analysis(call_id: str, transcript: str, summary: str, outcome: str, analysis: dict, lead_id: str | None = None, campaign_id: str | None = None):
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
            call.transcript = transcript # type: ignore
            call.ai_summary = summary # type: ignore
            call.outcome = outcome # type: ignore
            call.status = "completed" # type: ignore
            call.recording_url = analysis.get("recording_url") # type: ignore
            call.objection_raised = analysis.get("objection_raised") # type: ignore
            
            if outcome == "meeting_booked":
                call.meeting_booked = True # type: ignore
                
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
    from app.core.config import get_settings
    settings = get_settings()
    prospect_email = None
    
    # Fetch phone & email from DB if missing
    if lead_id:
        db = SessionLocal()
        try:
            lead = db.query(Lead).filter(Lead.id == uuid.UUID(lead_id)).first()
            if lead:
                prospect_phone = lead.phone or prospect_phone
                prospect_email = lead.email
                if not prospect_name:
                    prospect_name = lead.full_name or "there"
        finally:
            db.close()
            
    if not prospect_phone:
        print("Skipping post call actions: No phone number available.")
        return

    booking_url = settings.GMEET_LINK or "https://calendar.google.com/calendar/u/0/appointments/schedules/AcZssZ35QI8Gc4MbVP5DQSfV6bJ7xeH746aG8NnJyxNR95p07BHpHKMY6guW7V5fgZRsIZCDGaaHQawv"

    if outcome in ["meeting_booked", "interested_callback"]:
        # 1. Send SMS/WhatsApp Booking Link
        msg = (f"Hi {prospect_name}! Great speaking with you today. Here is the link to schedule "
               f"your free 15-minute digital growth audit: {booking_url}. Looking forward to connecting!")
        
        await sms_service.send(prospect_phone, msg)
        await whatsapp_service.send(prospect_phone, msg)
        await notify_rm_team(prospect_name, business or "Prospect Business", "Self-scheduling via Link", services or "Audit")
        
        # 2. Send Email Booking Link via SMTP
        if prospect_email:
            try:
                from app.utils.automations import send_smtp_email_direct
                subject = "Schedule your Reach Magnets digital growth audit"
                html_content = f"""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333; background-color: #f9f9f9; padding: 20px;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 30px; background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                        <h2 style="color: #6C5DD3; margin-top: 0; font-size: 20px;">Hi {prospect_name},</h2>
                        <p style="font-size: 15px; margin-bottom: 18px;">Great speaking with you on the phone today!</p>
                        <p style="font-size: 15px; margin-bottom: 18px;">As discussed, here is the link to schedule your free 15-minute digital growth audit. Please select a time that fits your schedule best:</p>
                        <div style="margin: 30px 0; text-align: center;">
                            <a href="{booking_url}" style="background-color: #6C5DD3; color: #ffffff; display: inline-block; font-weight: bold; font-size: 15px; padding: 14px 28px; text-decoration: none; border-radius: 8px; box-shadow: 0 4px 12px rgba(108, 93, 211, 0.25);">
                                Schedule My Appointment ➔
                            </a>
                        </div>
                        <p style="font-size: 13px; color: #666666; margin-top: 25px;">If you have any questions or need to make changes, feel free to reply directly to this email.</p>
                        <p style="margin-bottom: 0; font-size: 14px; color: #333333;">Best regards,<br><strong>Reach Magnets Team</strong></p>
                    </div>
                </body>
                </html>
                """
                await send_smtp_email_direct(str(prospect_email), subject, html_content)
            except Exception as e:
                print(f"Error sending SMTP booking link email: {e}")
        
    elif outcome in ["no_answer", "voicemail", "busy", "failed"]:
        msg = (f"Hi {prospect_name}, we tried calling from Reach Magnets about helping {business or 'your business'} "
               f"get more customers. If you are interested in a free local search audit, reply YES or visit reachmagnets.com!")
        await sms_service.send(prospect_phone, msg)
        
    elif outcome == "not_interested":
        msg = (f"Hi {prospect_name}, thank you for your time today. If you ever want to increase your customer inquiries "
               f"or optimize your search listing, visit our service at reachmagnets.com. Have a great day!")
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
    
    # Custom fields collected from Ojas mid-call:
    phone = data.get("prospect_phone")
    business_name = data.get("business_name")
    zip_code = data.get("zip_code")
    
    # Book on Google Meet
    booking = await gmeet_service.book_slot(
        name=name,
        email=email,
        date=preferred_date,
        time=preferred_time
    )
    
    if booking["success"]:
        db = SessionLocal()
        try:
            cleaned_email = clean_email_address(email) if email else None
            
            lead = None
            if cleaned_email:
                lead = db.query(Lead).filter(Lead.email == cleaned_email).first()
            if not lead and name:
                lead = db.query(Lead).filter(Lead.full_name.ilike(f"%{name}%")).first()
            
            call_obj = data.get("call", {})
            phone_num = call_obj.get("to_number") or ""
            target_phone = phone or phone_num
            
            if not lead and target_phone:
                lead = db.query(Lead).filter(Lead.phone == target_phone).first()
                
            if not lead:
                lead = Lead(
                    full_name=name or "Unknown Prospect",
                    email=cleaned_email or "unknown@example.com",
                    phone=target_phone or "+1000000000",
                    business_name=business_name or "",
                    zip_code=zip_code,
                    status="meeting_booked",
                    source="inbound_booking"
                )
                db.add(lead)
                db.flush()
            else:
                if name and (not lead.full_name or lead.full_name == "Prospect"):
                    lead.full_name = name  # type: ignore
                if cleaned_email and (not lead.email or lead.email == "unknown@example.com"):
                    lead.email = cleaned_email  # type: ignore
                if target_phone and not lead.phone:
                    lead.phone = target_phone  # type: ignore
                if business_name and not lead.business_name:
                    lead.business_name = business_name  # type: ignore
                if zip_code:
                    lead.zip_code = zip_code  # type: ignore
                lead.status = "meeting_booked"  # type: ignore
            
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
                prospect_email=lead.email or email,
                prospect_business=lead.business_name or "",
                meeting_date=m_date,
                meeting_time=preferred_time,
                cal_meeting_link=booking["link"],
                status="confirmed"
            )
            db.add(appt)
            lead.status = "meeting_booked" # type: ignore
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
