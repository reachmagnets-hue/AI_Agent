import asyncio
import random
import uuid
import structlog
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.models.lead import Lead
from app.models.campaign import Campaign

logger = structlog.get_logger(__name__)

TEMPLATES = [
    # Template 1: Meeting Booked
    {
        "outcome": "meeting_booked",
        "duration": 78,
        "transcript": (
            "Ojas: Hi! Is this {business_name}?\n"
            "Prospect: Yes, it is. How can I help you?\n"
            "Ojas: Hi, this is Ojas from Reach Magnets. I noticed many businesses in your area are investing heavily in local search and reviews recently, and it made me curious. How are you currently getting most of your new customers at {business_name}?\n"
            "Prospect: Mostly referrals, but we've been trying to get more reviews on Google.\n"
            "Ojas: That makes perfect sense. Reviews are huge. We recently helped a local business increase customer inquiries by 37% in three months by optimizing their search. We do a free 15-minute digital growth audit to show you where you're losing customers to competitors. Would you be open to a quick 15-minute strategy call next week?\n"
            "Prospect: Sure, that sounds interesting. Tuesday afternoon works.\n"
            "Ojas: Perfect! Let me get that booked for you right now... What's the best email for the calendar invitation?\n"
            "Prospect: Send it to {email}.\n"
            "Ojas: Excellent! You're confirmed for next Tuesday. Talk soon!"
        ),
        "summary": "Prospect agreed to a 15-minute digital growth audit on next Tuesday afternoon. Confirmed email for calendar invitation.",
        "prospect_name": "{full_name}",
        "services_interested": "Google Reviews and Local Search Optimization",
        "meeting_datetime": "Next Tuesday at 2:00 PM",
        "lead_score_status": "Interested",
        "is_decision_maker": "Yes"
    },
    # Template 2: Interested Callback
    {
        "outcome": "interested_callback",
        "duration": 45,
        "transcript": (
            "Ojas: Hi! Is this {business_name}?\n"
            "Prospect: Yes, this is {full_name}.\n"
            "Ojas: Hi! This is Ojas from Reach Magnets. How are you getting new customers?\n"
            "Prospect: We do some social media, but we are too busy to talk right now.\n"
            "Ojas: I understand. We do a free 15-minute local growth report showing where you stand. Could I send you an email with the report so you can look at it later?\n"
            "Prospect: Sure, email it to me at {email}.\n"
            "Ojas: Great! I'll send that over. Have a wonderful day!"
        ),
        "summary": "Prospect is busy but requested a free local growth report via email. Will follow up.",
        "prospect_name": "{full_name}",
        "services_interested": "SEO Audit",
        "meeting_datetime": "",
        "lead_score_status": "Interested",
        "is_decision_maker": "Yes"
    },
    # Template 3: Not Interested
    {
        "outcome": "not_interested",
        "duration": 22,
        "transcript": (
            "Ojas: Hi! Is this {business_name}?\n"
            "Prospect: Yes.\n"
            "Ojas: This is Ojas from Reach Magnets. How do you get new customers?\n"
            "Prospect: We don't do any marketing, we're not interested. Thanks.\n"
            "Ojas: Understood. Thanks for your time!"
        ),
        "summary": "Prospect stated they are not interested in marketing services and hung up.",
        "prospect_name": "",
        "services_interested": "",
        "meeting_datetime": "",
        "lead_score_status": "Not interested",
        "is_decision_maker": "Uncertain"
    },
    # Template 4: Voicemail
    {
        "outcome": "voicemail",
        "duration": 12,
        "transcript": "Voicemail: Please leave a message after the tone. [Beep]",
        "summary": "Call went to voicemail. No message left.",
        "prospect_name": "",
        "services_interested": "",
        "meeting_datetime": "",
        "lead_score_status": "Neutral",
        "is_decision_maker": "Uncertain"
    }
]

async def simulate_call_lifecycle(lead_id: str, campaign_id: str, call_id: str):
    """Simulates the lifecycle of a Retell call by calling the webhook logic steps after short delays."""
    from app.routers.retell_webhook import (
        update_lead_status,
        create_call_record,
        update_call_duration,
        save_call_analysis,
        handle_post_call_actions
    )
    
    db = SessionLocal()
    lead = None
    try:
        lead = db.query(Lead).filter(Lead.id == uuid.UUID(str(lead_id))).first()
        if not lead:
            logger.error("Simulation: Lead not found", lead_id=str(lead_id))
            return
        
        business_name = lead.business_name or "your business"
        full_name = lead.full_name or "prospect"
        email = lead.email or "contact@example.com"
        phone = lead.phone or "+1000000000"
    finally:
        db.close()
        
    logger.info("Starting simulated call lifecycle", lead_id=str(lead_id), call_id=call_id)
    
    # 1. Simulate Call Started event
    logger.info("Simulation: Sending call_started event", call_id=call_id)
    update_lead_status(str(lead_id), "calling")
    
    call_data = {
        "from_number": "+13185953306",
        "to_number": phone
    }
    create_call_record(call_id, str(lead_id), call_data)
    
    # Wait 4 seconds to simulate call duration
    await asyncio.sleep(4)
    
    # Choose simulated outcome randomly for a realistic campaign distribution
    rand_val = random.random()
    if rand_val < 0.15:
        template = TEMPLATES[0]  # meeting_booked
    elif rand_val < 0.30:
        template = TEMPLATES[1]  # interested_callback
    else:
        # Default to non-booking outcomes (not_interested, voicemail, no_answer)
        non_booking_options = [TEMPLATES[2], TEMPLATES[3]]
        no_answer_option = {
            "outcome": "no_answer",
            "duration": 0,
            "transcript": "",
            "summary": "Called prospect but no answer.",
            "prospect_name": "",
            "services_interested": "",
            "meeting_datetime": "",
            "lead_score_status": "Neutral",
            "is_decision_maker": "Uncertain"
        }
        all_options = non_booking_options + [no_answer_option]
        template = random.choice(all_options)
    
    # Format fields
    transcript = template["transcript"].format(
        business_name=business_name,
        full_name=full_name,
        email=email
    )
    summary = template["summary"]
    outcome = template["outcome"]
    duration = template["duration"]
    
    prospect_name = template["prospect_name"].format(full_name=full_name) if template["prospect_name"] else ""
    services = template["services_interested"]
    meeting_dt = template["meeting_datetime"]
    
    # 2. Simulate Call Ended event
    logger.info("Simulation: Sending call_ended event", call_id=call_id)
    update_call_duration(call_id, duration)
    update_lead_status(str(lead_id), "called")
    
    # Wait 2 seconds before sending analysis
    await asyncio.sleep(2)
    
    # 3. Simulate Call Analyzed event
    logger.info("Simulation: Sending call_analyzed event", call_id=call_id)
    custom_analysis = {
        "outcome": outcome,
        "prospect_name": prospect_name,
        "business_name": business_name,
        "services_interested": services,
        "meeting_datetime": meeting_dt,
        "lead_score_status": template["lead_score_status"],
        "is_decision_maker": template["is_decision_maker"],
        "objection_raised": "None" if outcome in ["meeting_booked", "interested_callback"] else "Not interested"
    }
    
    save_call_analysis(
        call_id=call_id,
        transcript=transcript,
        summary=summary,
        outcome=outcome,
        analysis={
            "recording_url": "https://api.retellai.com/recordings/mock.mp3",
            "objection_raised": custom_analysis["objection_raised"]
        },
        lead_id=str(lead_id),
        campaign_id=str(campaign_id)
    )
    
    # Update lead details based on outcome
    from app.routers.retell_webhook import update_lead_from_analysis
    status_map = {
        "meeting_booked": "meeting_booked",
        "interested_callback": "interested",
        "not_interested": "not_interested",
        "no_answer": "no_answer",
        "voicemail": "voicemail"
    }
    update_lead_from_analysis(str(lead_id), status_map.get(outcome, "called"), custom_analysis, summary)
    
    if outcome == "meeting_booked":
        from app.models.appointment import Appointment
        from datetime import date, timedelta
        from app.models.call import Call
        db = SessionLocal()
        try:
            call_obj = db.query(Call).filter(Call.retell_call_id == call_id).first()
            call_db_id = call_obj.id if call_obj else None
            
            appt = Appointment(
                lead_id=uuid.UUID(str(lead_id)),
                call_id=call_db_id,
                campaign_id=uuid.UUID(str(campaign_id)) if campaign_id else None,
                title="Discovery Call - Reach Magnets",
                prospect_name=prospect_name or "Prospect",
                prospect_phone=phone,
                prospect_email=email,
                prospect_business=business_name,
                meeting_date=date.today() + timedelta(days=random.randint(1, 5)),
                meeting_time=random.choice(["10:00 AM", "11:30 AM", "2:00 PM", "4:30 PM"]),
                timezone="America/New_York",
                duration_minutes=15,
                cal_meeting_link="https://meet.google.com/mock-meet-link",
                status="confirmed",
                discussion_summary=summary,
                services_interested=services
            )
            db.add(appt)
            db.commit()
            logger.info("Simulation: Created Appointment record", lead_id=str(lead_id))
        except Exception as appt_err:
            logger.error("Simulation: Error creating appointment record", error=str(appt_err))
        finally:
            db.close()
            
    # Send WebSocket update
    from app.core.websocket import websocket_manager
    await websocket_manager.broadcast({
        "event": "lead_status_updated",
        "lead_id": str(lead_id),
        "status": status_map.get(outcome, "called"),
        "outcome": outcome,
        "prospect_name": prospect_name,
        "business_name": business_name,
        "call_id": call_id
    })
    
    # Handle post call actions
    await handle_post_call_actions(
        outcome=outcome,
        lead_id=str(lead_id),
        prospect_name=prospect_name,
        prospect_phone=call_data["to_number"],
        business=business_name,
        services=services,
        meeting_dt=meeting_dt,
        summary=summary
    )
    
    logger.info("Simulation complete for call", call_id=call_id, outcome=outcome)
