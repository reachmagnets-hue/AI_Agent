import os
import structlog
from typing import Dict, Any, Optional, cast
from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# Try to import Retell client
try:
    from retell import Retell
    RETELL_AVAILABLE = True
except ImportError:
    RETELL_AVAILABLE = False
    logger.warning("Retell module not available. Outbound calling will be mocked.")

class RetellService:
    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.RETELL_API_KEY
        self.agent_id = self.settings.RETELL_AGENT_ID
        self.from_number = self.settings.TWILIO_PHONE_NUMBER
        
        self.client = None
        if RETELL_AVAILABLE and self.api_key and self.api_key != "your_retell_api_key":
            try:
                self.client = Retell(api_key=self.api_key)
            except Exception as e:
                logger.error("Failed to initialize Retell client", error=str(e))

    def is_configured(self) -> bool:
        """Check if Retell service is properly configured"""
        return bool(self.client and self.agent_id)

    async def make_call(self, phone_number: str, campaign_id: str, contact_id: str) -> Dict[str, Any]:
        """Initiate an outbound call using Retell AI"""
        logger.info("Initiating Retell outbound call", phone_number=phone_number, campaign_id=campaign_id, contact_id=contact_id)
        
        if not self.client or not self.agent_id:
            logger.warning("Retell service not configured. Returning mock call details.")
            import uuid
            return {
                "call_id": f"mock_retell_{uuid.uuid4()}",
                "call_status": "registered",
                "mocked": True
            }
        
        try:
            # Use retell SDK — metadata must use lead_id (not contact_id) so webhook can match
            phone_call = self.client.call.create_phone_call(
                from_number=self.from_number,
                to_number=phone_number,
                override_agent_id=self.agent_id,
                metadata={
                    "lead_id": contact_id,       # webhook expects lead_id
                    "campaign_id": campaign_id
                }
            )
            
            logger.info("Retell call created successfully", call_id=phone_call.call_id, status=phone_call.call_status)
            return {
                "call_id": phone_call.call_id,
                "call_status": phone_call.call_status,
                "mocked": False
            }
        except Exception as e:
            logger.error("Error creating Retell call", error=str(e), exc_info=True)
            raise e

    async def get_call_details(self, call_id: str) -> Dict[str, Any]:
        """Get detailed call information from Retell"""
        if not self.client or not self.agent_id or call_id.startswith("mock_"):
            return {"call_id": call_id, "call_status": "completed", "duration_ms": 30000, "transcript": "Mock call completed."}
            
        try:
            # SDK uses .retrieve(), not .retrieve_phone_call()
            phone_call = self.client.call.retrieve(call_id)
            return {
                "call_id": phone_call.call_id,
                "call_status": phone_call.call_status,
                "duration_ms": getattr(phone_call, 'duration_ms', 0),
                "transcript": getattr(phone_call, 'transcript', ''),
                "recording_url": getattr(phone_call, 'recording_url', None),
                "call_analysis": getattr(phone_call, 'call_analysis', {})
            }
        except Exception as e:
            logger.error("Error retrieving Retell call details", call_id=call_id, error=str(e))
            raise e

# HTTPX integrations for dynamic Sarah agent management
import httpx

RETELL_BASE_URL = "https://api.retellai.com"

def get_headers() -> dict:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.RETELL_API_KEY}",
        "Content-Type": "application/json"
    }

# Agent Config template for Cartesia Sarah
AGENT_CONFIG = {
    "agent_name": "Ojas - Reach Magnets",
    "voice_id": "cartesia-Sarah",
    "llm_websocket_url": None,
    "retell_llm_dynamic_variables": {},
    "response_engine": {
        "type": "retell-llm",
        "llm_id": ""  # will be filled after creating LLM
    },
    "language": "en-US",
    "opt_out_sensitive_data_storage": False,
    "enable_backchannel": True,
    "ambient_sound": "coffee-shop",
    "backchannel_frequency": 0.7,
    "backchannel_words": ["right", "got it", "I see", "absolutely", "of course"],
    "reminder_trigger_ms": 10000,
    "reminder_max_count": 2,
    "interruption_sensitivity": 0.8,
    "end_call_after_silence_ms": 30000,
    "max_call_duration_ms": 600000,
    "post_call_analysis_data": [
        {
            "name": "outcome",
            "type": "enum",
            "description": "What was the result of this call?",
            "choices": [
                "meeting_booked",
                "interested_callback", 
                "not_interested",
                "no_answer",
                "voicemail",
                "wrong_number"
            ]
        },
        {
            "name": "prospect_name",
            "type": "string",
            "description": "Full name of the prospect spoken on call"
        },
        {
            "name": "business_name", 
            "type": "string",
            "description": "Business name mentioned by prospect"
        },
        {
            "name": "services_interested",
            "type": "string", 
            "description": "Which services prospect showed interest in"
        },
        {
            "name": "meeting_datetime",
            "type": "string",
            "description": "If meeting booked, the date and time agreed"
        },
        {
            "name": "lead_score_status",
            "type": "enum",
            "description": "Determine the lead score rating category based on their interest.",
            "choices": ["Interested", "Neutral", "Not interested"]
        },
        {
            "name": "is_decision_maker",
            "type": "enum",
            "description": "Is this prospect the decision maker for marketing/business decisions?",
            "choices": ["Yes", "No", "Uncertain"]
        },
        {
            "name": "objection_raised",
            "type": "string",
            "description": "Main objection prospect raised if any"
        },
        {
            "name": "prospect_email",
            "type": "string",
            "description": "Email address of the prospect spoken on call"
        },
        {
            "name": "prospect_phone",
            "type": "string",
            "description": "Phone number or mobile number of the prospect spoken on call"
        },
        {
            "name": "zip_code",
            "type": "string",
            "description": "Zip code of the business or prospect"
        }
    ]
}

async def create_retell_llm() -> str:
    """Create the LLM config in Retell — returns llm_id"""
    settings = get_settings()
    SALES_PROMPT = """
You are Ojas, a warm, professional, and consultative growth advisor calling on behalf of Reach Magnets — a digital marketing agency helping US businesses attract more customers online.

YOUR IDENTITY & STYLE:
- Name: Ojas | Company: Reach Magnets | Role: Growth Advisor
- Voice/Tone: Friendly, natural, curious, consultative — NOT a pushy telemarketer.
- Speaking Rules: Keep every response under 1–2 sentences. Always ask a question to listen and keep the prospect speaking 60-70% of the time.
- Interruption Rule: If the prospect interrupts you, STOP speaking immediately. Do not talk over them.

YOUR ONE GOAL & REQUIRED INFO TO COLLECT:
Your goal is to book a free 15-minute marketing audit and strategy call with the Reach Magnets specialist team.
To do this, you MUST systematically collect and verify the following 5 details during the call:
1. Person's Name: Ask for their first and last name.
2. Business Name: Confirm their business name (e.g. if they say "Yeah, this is Joe's Dental", verify it).
3. Primary Phone Number: Confirm their primary contact number to reach them or send the calendar link.
4. Email Address: Ask for their primary email. Strictly repeat it back domain-by-domain or letter-by-letter to verify spelling. Watch out for typos (e.g. correct 'gmails.com' to 'gmail.com'). Do not accept fake/placeholder emails like 'example@gmail' or 'contact@gmail.com'. Ask for a valid email where they can receive the calendar invitation.
5. Zip Code: Ask for their business or local zip code.

CONVERSATION FLOW:
1. Hook (Curiosity Loop): "I noticed many businesses in your area are investing heavily in local search and reviews recently, and it made me curious about how your business is doing. How are you currently getting most of your new customers at [business_name]?"
2. Discovery: Learn about their client channels, whether they run online ads, and what their primary customer acquisition challenges are.
3. Social Proof & Pitch: Pitch ONLY after identifying a challenge or gap. Use localized proof: "We recently helped a local business increase customer inquiries by 37% in three months by optimizing their local search. We actually do a free 15-minute digital growth audit to show you where you're losing customers to competitors."
4. Call to Action: "Would you be open to a quick 15-minute strategy call next week?" If they say yes, immediately proceed to collect the 5 details above.

INDUSTRY-SPECIFIC SCRIPTS (Adhere to this based on the business type or industry):
- Dentist: Focus on local search ranking, new patient bookings, and Google reviews. Social Proof: "Helped a family dentist get 15 new patient appointments in their first month."
- Salon: Focus on repeat clients, Instagram presence, and online booking flow. Social Proof: "Helped a local salon increase bookings by 37% in three months."
- Real Estate: Focus on lead generation, Facebook ad campaigns, and landing pages. Social Proof: "Helped an agent capture 24 qualified seller leads in 30 days."
- Restaurant: Focus on online reviews, Google Maps ranking, and delivery app visibility. Social Proof: "Boosted Google Maps clicks by 45% for a local diner."
- Local Services (Plumbing, Roofing, HVAC): Focus on inbound emergency calls and Google Local Service Ads. Social Proof: "Doubled a roofing client's high-value quote requests in 90 days."

OBJECTION HANDLING MATRIX:
- "Not interested." -> "I understand. Before I let you go, can I ask how you're currently generating new customers?"
- "We already have an agency." -> "That's great. Are you completely satisfied with the results they're delivering?"
- "Send me an email." -> "Happy to. What would be most useful for me to include so it's relevant to your business?"
- "We don't need marketing." -> "That's good to hear. What are the main channels bringing you customers today?"
- "Too expensive." -> "Understood. Is budget the main concern, or are you unsure about the potential return?"
- "We're busy." -> "I can appreciate that. Would a quick 30-second overview help determine if it's worth revisiting later?"
- "Call back later." -> "Certainly. When would be a better time, and what should I prepare before then?"
- "We get enough leads." -> "That's excellent. Are you looking to maintain that level or grow further this year?"
- "We tried marketing before." -> "Many businesses have. What do you think didn't work well last time?"
- "I make those decisions myself." -> "Perfect. You're exactly the person I was hoping to speak with."
- "We only use referrals." -> "Referrals are valuable. Have you considered ways to supplement them during slower periods?"
- "We don't advertise online." -> "Is that a deliberate strategy, or something you've simply never needed to explore?"
- "We don't have time." -> "That's fair. What business priority is taking most of your attention right now?"
- "We're a small business." -> "Many of our clients started small. What growth goals do you have over the next year?"
- "How did you get my number?" -> "We work with businesses in your area and found your public business contact information."
- "We're not looking right now." -> "Understood. What would need to change before you'd consider exploring new options?"
- "Is this a sales call?" -> "Yes, but my goal is first to understand whether there's any potential fit."
- "I don't trust marketing companies." -> "I hear that often. What experiences have shaped that view?"
- "We don't need a website." -> "Are most of your customers finding you through other channels today?"
- "Google Ads don't work." -> "What was your experience when you used them previously?"
- "Facebook doesn't work for us." -> "That's possible. Which marketing channels have produced the best results for you?"
- "We don't have budget this quarter." -> "Understood. Are you planning any growth initiatives for the next quarter?"
- "We do everything in-house." -> "That's impressive. How much time does your team spend on marketing activities each week?"
- "We are happy with our rankings." -> "That's great. Are there any keywords or services where you'd still like greater visibility?"
- "We're too small for this." -> "Sometimes smaller businesses see the biggest gains from focused local marketing."
- "Nobody answers marketing calls." -> "That's exactly why we're focused on understanding what actually works for businesses like yours."
- "I need to discuss with my partner." -> "Makes sense. What questions do you think your partner would want answered?"
- "We don't see ROI from marketing." -> "Measuring ROI is critical. How are you currently tracking marketing performance?"
- "We are seasonal." -> "Interesting. How do you typically generate demand during slower periods?"
- "We're closing soon." -> "Thanks for letting me know. Before I go, is there a better time to reconnect?"

LEAD SCORING & TRANSITION:
Identify prospect alignment: Interested, Neutral, or Not interested. Also identify if they are the Decision Maker. When interest is detected, immediately steer to book the appointment: "Would you be open to a 15-minute strategy call with our specialist next week?"
"""
    from retell import Retell
    client = Retell(api_key=settings.RETELL_API_KEY)
    
    llm = client.llm.create(
        model=cast(Any, "gpt-4o"),
        general_prompt=SALES_PROMPT,
        begin_message="Hi! Is this [business_name]?",
        general_tools=[
            {
                "type": "end_call",
                "name": "end_call",
                "description": "End the call when conversation is complete, prospect said goodbye, or is clearly not interested after 2 attempts."
            },
            {
                "type": "custom",
                "name": "book_appointment",
                "description": "Book a discovery call when prospect agrees to meet. Call this immediately when they say yes to a meeting. You must collect name, phone, email, business name, and zip code to book.",
                "speak_during_execution": True,
                "speak_after_execution": True,
                "execution_message_description": "Say: 'Perfect! Let me get that booked for you right now...'",
                "url": f"{settings.BASE_URL}/api/retell/book-appointment",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prospect_name": {
                            "type": "string",
                            "description": "Full name of prospect"
                        },
                        "prospect_email": {
                            "type": "string", 
                            "description": "Email address for calendar invite"
                        },
                        "prospect_phone": {
                            "type": "string",
                            "description": "Primary phone number of prospect"
                        },
                        "business_name": {
                            "type": "string",
                            "description": "Company or business name"
                        },
                        "zip_code": {
                            "type": "string",
                            "description": "5-digit zip code of the business location"
                        },
                        "preferred_date": {
                            "type": "string",
                            "description": "Preferred meeting date e.g. 'next Tuesday' or '2026-05-27'"
                        },
                        "preferred_time": {
                            "type": "string",
                            "description": "Preferred time e.g. '2pm' or '14:00'"
                        }
                    },
                    "required": ["prospect_name", "prospect_email", "prospect_phone", "business_name", "zip_code"]
                }
            }
        ]
    )
    return llm.llm_id

async def create_retell_agent(llm_id: str) -> str:
    """Create the Retell agent — returns agent_id"""
    settings = get_settings()
    from retell import Retell
    client = Retell(api_key=settings.RETELL_API_KEY)
    
    agent = client.agent.create(
        agent_name="Ojas - Reach Magnets",
        voice_id="cartesia-Sarah",
        response_engine={
            "type": "retell-llm",
            "llm_id": llm_id
        },
        language="en-US",
        enable_backchannel=True,
        ambient_sound="coffee-shop",
        backchannel_frequency=0.7,
        backchannel_words=["right", "got it", "I see", "absolutely", "of course"],
        reminder_trigger_ms=10000,
        reminder_max_count=2,
        interruption_sensitivity=0.8,
        end_call_after_silence_ms=30000,
        max_call_duration_ms=600000,
        post_call_analysis_data=[
            {
                "name": "outcome",
                "type": "enum",
                "description": "What was the result of this call?",
                "choices": [
                    "meeting_booked",
                    "interested_callback", 
                    "not_interested",
                    "no_answer",
                    "voicemail",
                    "wrong_number"
                ]
            },
            {
                "name": "prospect_name",
                "type": "string",
                "description": "Full name of the prospect spoken on call"
            },
            {
                "name": "business_name", 
                "type": "string",
                "description": "Business name mentioned by prospect"
            },
            {
                "name": "services_interested",
                "type": "string", 
                "description": "Which services prospect showed interest in"
            },
            {
                "name": "meeting_datetime",
                "type": "string",
                "description": "If meeting booked, the date and time agreed"
            },
            {
                "name": "lead_score_status",
                "type": "enum",
                "description": "Determine the lead score rating category based on their interest.",
                "choices": ["Interested", "Neutral", "Not interested"]
            },
            {
                "name": "is_decision_maker",
                "type": "enum",
                "description": "Is this prospect the decision maker for marketing/business decisions?",
                "choices": ["Yes", "No", "Uncertain"]
            },
            {
                "name": "objection_raised",
                "type": "string",
                "description": "Main objection prospect raised if any"
            },
            {
                "name": "prospect_email",
                "type": "string",
                "description": "Email address of the prospect spoken on call"
            },
            {
                "name": "prospect_phone",
                "type": "string",
                "description": "Phone number or mobile number of the prospect spoken on call"
            },
            {
                "name": "zip_code",
                "type": "string",
                "description": "Zip code of the business or prospect"
            }
        ]
    )
    return agent.agent_id

async def setup_retell_agent() -> dict:
    """
    Master function — run once to create everything.
    Returns llm_id and agent_id to save in .env
    """
    print("Creating Retell LLM...")
    llm_id = await create_retell_llm()
    print(f"LLM created: {llm_id}")
    
    print("Creating Retell Agent...")
    agent_id = await create_retell_agent(llm_id)
    print(f"Agent created: {agent_id}")
    
    print("\n=== SAVE THESE IN YOUR .env ===")
    print(f"RETELL_LLM_ID={llm_id}")
    print(f"RETELL_AGENT_ID={agent_id}")
    
    return {"llm_id": llm_id, "agent_id": agent_id}

async def update_existing_retell_agent() -> dict:
    """
    Updates the existing Retell LLM and Agent configurations using the IDs from .env
    """
    settings = get_settings()
    llm_id = settings.RETELL_LLM_ID
    agent_id = settings.RETELL_AGENT_ID
    
    if not llm_id or not agent_id or llm_id.startswith("your_") or agent_id.startswith("your_"):
        print("Missing or placeholder RETELL_LLM_ID or RETELL_AGENT_ID in .env. Running full setup instead...")
        return await setup_retell_agent()
        
    print(f"Updating existing Retell LLM: {llm_id}...")
    from retell import Retell
    client = Retell(api_key=settings.RETELL_API_KEY)
    
    # Generate same sales prompt with Ojas
    # We will reuse the SALES_PROMPT logic from create_retell_llm but inline it or get it
    # Since SALES_PROMPT is local to create_retell_llm, we can write a helper function _get_ojas_prompt()
    # Or just write it out:
    prompt = """
You are Ojas, a warm, professional, and consultative growth advisor calling on behalf of Reach Magnets — a digital marketing agency helping US businesses attract more customers online.

YOUR IDENTITY & STYLE:
- Name: Ojas | Company: Reach Magnets | Role: Growth Advisor
- Voice/Tone: Friendly, natural, curious, consultative — NOT a pushy telemarketer.
- Speaking Rules: Keep every response under 1–2 sentences. Always ask a question to listen and keep the prospect speaking 60-70% of the time.
- Interruption Rule: If the prospect interrupts you, STOP speaking immediately. Do not talk over them.

YOUR ONE GOAL & REQUIRED INFO TO COLLECT:
Your goal is to book a free 15-minute marketing audit and strategy call with the Reach Magnets specialist team.
To do this, you MUST systematically collect and verify the following 5 details during the call:
1. Person's Name: Ask for their first and last name.
2. Business Name: Confirm their business name (e.g. if they say "Yeah, this is Joe's Dental", verify it).
3. Primary Phone Number: Confirm their primary contact number to reach them or send the calendar link.
4. Email Address: Ask for their primary email. Strictly repeat it back domain-by-domain or letter-by-letter to verify spelling. Watch out for typos (e.g. correct 'gmails.com' to 'gmail.com'). Do not accept fake/placeholder emails like 'example@gmail' or 'contact@gmail.com'. Ask for a valid email where they can receive the calendar invitation.
5. Zip Code: Ask for their business or local zip code.

CONVERSATION FLOW:
1. Hook (Curiosity Loop): "I noticed many businesses in your area are investing heavily in local search and reviews recently, and it made me curious about how your business is doing. How are you currently getting most of your new customers at [business_name]?"
2. Discovery: Learn about their client channels, whether they run online ads, and what their primary customer acquisition challenges are.
3. Social Proof & Pitch: Pitch ONLY after identifying a challenge or gap. Use localized proof: "We recently helped a local business increase customer inquiries by 37% in three months by optimizing their local search. We actually do a free 15-minute digital growth audit to show you where you're losing customers to competitors."
4. Call to Action: "Would you be open to a quick 15-minute strategy call next week?" If they say yes, immediately proceed to collect the 5 details above.

INDUSTRY-SPECIFIC SCRIPTS (Adhere to this based on the business type or industry):
- Dentist: Focus on local search ranking, new patient bookings, and Google reviews. Social Proof: "Helped a family dentist get 15 new patient appointments in their first month."
- Salon: Focus on repeat clients, Instagram presence, and online booking flow. Social Proof: "Helped a local salon increase bookings by 37% in three months."
- Real Estate: Focus on lead generation, Facebook ad campaigns, and landing pages. Social Proof: "Helped an agent capture 24 qualified seller leads in 30 days."
- Restaurant: Focus on online reviews, Google Maps ranking, and delivery app visibility. Social Proof: "Boosted Google Maps clicks by 45% for a local diner."
- Local Services (Plumbing, Roofing, HVAC): Focus on inbound emergency calls and Google Local Service Ads. Social Proof: "Doubled a roofing client's high-value quote requests in 90 days."

OBJECTION HANDLING MATRIX:
- "Not interested." -> "I understand. Before I let you go, can I ask how you're currently generating new customers?"
- "We already have an agency." -> "That's great. Are you completely satisfied with the results they're delivering?"
- "Send me an email." -> "Happy to. What would be most useful for me to include so it's relevant to your business?"
- "We don't need marketing." -> "That's good to hear. What are the main channels bringing you customers today?"
- "Too expensive." -> "Understood. Is budget the main concern, or are you unsure about the potential return?"
- "We're busy." -> "I can appreciate that. Would a quick 30-second overview help determine if it's worth revisiting later?"
- "Call back later." -> "Certainly. When would be a better time, and what should I prepare before then?"
- "We get enough leads." -> "That's excellent. Are you looking to maintain that level or grow further this year?"
- "We tried marketing before." -> "Many businesses have. What do you think didn't work well last time?"
- "I make those decisions myself." -> "Perfect. You're exactly the person I was hoping to speak with."
- "We only use referrals." -> "Referrals are valuable. Have you considered ways to supplement them during slower periods?"
- "We don't advertise online." -> "Is that a deliberate strategy, or something you've simply never needed to explore?"
- "We don't have time." -> "That's fair. What business priority is taking most of your attention right now?"
- "We're a small business." -> "Many of our clients started small. What growth goals do you have over the next year?"
- "How did you get my number?" -> "We work with businesses in your area and found your public business contact information."
- "We're not looking right now." -> "Understood. What would need to change before you'd consider exploring new options?"
- "Is this a sales call?" -> "Yes, but my goal is first to understand whether there's any potential fit."
- "I don't trust marketing companies." -> "I hear that often. What experiences have shaped that view?"
- "We don't need a website." -> "Are most of your customers finding you through other channels today?"
- "Google Ads don't work." -> "What was your experience when you used them previously?"
- "Facebook doesn't work for us." -> "That's possible. Which marketing channels have produced the best results for you?"
- "We don't have budget this quarter." -> "Understood. Are you planning any growth initiatives for the next quarter?"
- "We do everything in-house." -> "That's impressive. How much time does your team spend on marketing activities each week?"
- "We are happy with our rankings." -> "That's great. Are there any keywords or services where you'd still like greater visibility?"
- "We're too small for this." -> "Sometimes smaller businesses see the biggest gains from focused local marketing."
- "Nobody answers marketing calls." -> "That's exactly why we're focused on understanding what actually works for businesses like yours."
- "I need to discuss with my partner." -> "Makes sense. What questions do you think your partner would want answered?"
- "We don't see ROI from marketing." -> "Measuring ROI is critical. How are you currently tracking marketing performance?"
- "We are seasonal." -> "Interesting. How do you typically generate demand during slower periods?"
- "We're closing soon." -> "Thanks for letting me know. Before I go, is there a better time to reconnect?"

LEAD SCORING & TRANSITION:
Identify prospect alignment: Interested, Neutral, or Not interested. Also identify if they are the Decision Maker. When interest is detected, immediately steer to book the appointment: "Would you be open to a 15-minute strategy call with our specialist next week?"
"""
    client.llm.update(
        llm_id=llm_id,
        general_prompt=prompt,
        begin_message="Hi! Is this [business_name]?",
        general_tools=[
            {
                "type": "end_call",
                "name": "end_call",
                "description": "End the call when conversation is complete, prospect said goodbye, or is clearly not interested after 2 attempts."
            },
            {
                "type": "custom",
                "name": "book_appointment",
                "description": "Book a discovery call when prospect agrees to meet. Call this immediately when they say yes to a meeting. You must collect name, phone, email, business name, and zip code to book.",
                "speak_during_execution": True,
                "speak_after_execution": True,
                "execution_message_description": "Say: 'Perfect! Let me get that booked for you right now...'",
                "url": f"{settings.BASE_URL}/api/retell/book-appointment",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prospect_name": {
                            "type": "string",
                            "description": "Full name of prospect"
                        },
                        "prospect_email": {
                            "type": "string", 
                            "description": "Email address for calendar invite"
                        },
                        "prospect_phone": {
                            "type": "string",
                            "description": "Primary phone number of prospect"
                        },
                        "business_name": {
                            "type": "string",
                            "description": "Company or business name"
                        },
                        "zip_code": {
                            "type": "string",
                            "description": "5-digit zip code of the business location"
                        },
                        "preferred_date": {
                            "type": "string",
                            "description": "Preferred meeting date e.g. 'next Tuesday' or '2026-05-27'"
                        },
                        "preferred_time": {
                            "type": "string",
                            "description": "Preferred time e.g. '2pm' or '14:00'"
                        }
                    },
                    "required": ["prospect_name", "prospect_email", "prospect_phone", "business_name", "zip_code"]
                }
            }
        ]
    )
    print("LLM updated successfully!")
    
    post_call_analysis_data = [
        {
            "name": "outcome",
            "type": "enum",
            "description": "What was the result of this call?",
            "choices": [
                "meeting_booked",
                "interested_callback", 
                "not_interested",
                "no_answer",
                "voicemail",
                "wrong_number"
            ]
        },
        {
            "name": "prospect_name",
            "type": "string",
            "description": "Full name of the prospect spoken on call"
        },
        {
            "name": "business_name", 
            "type": "string",
            "description": "Business name mentioned by prospect"
        },
        {
            "name": "services_interested",
            "type": "string", 
            "description": "Which services prospect showed interest in"
        },
        {
            "name": "meeting_datetime",
            "type": "string",
            "description": "If meeting booked, the date and time agreed"
        },
        {
            "name": "lead_score_status",
            "type": "enum",
            "description": "Determine the lead score rating category based on their interest.",
            "choices": ["Interested", "Neutral", "Not interested"]
        },
        {
            "name": "is_decision_maker",
            "type": "enum",
            "description": "Is this prospect the decision maker for marketing/business decisions?",
            "choices": ["Yes", "No", "Uncertain"]
        },
        {
            "name": "objection_raised",
            "type": "string",
            "description": "Main objection prospect raised if any"
        },
        {
            "name": "prospect_email",
            "type": "string",
            "description": "Email address of the prospect spoken on call"
        },
        {
            "name": "prospect_phone",
            "type": "string",
            "description": "Phone number or mobile number of the prospect spoken on call"
        },
        {
            "name": "zip_code",
            "type": "string",
            "description": "Zip code of the business or prospect"
        }
    ]
    
    client.agent.update(
        agent_id=agent_id,
        agent_name="Ojas - Reach Magnets",
        post_call_analysis_data=post_call_analysis_data  # type: ignore
    )
    print("Agent updated successfully!")
    return {"llm_id": llm_id, "agent_id": agent_id}

async def connect_phone_number(phone_number: str) -> dict:
    """
    Links your Twilio US number to the Retell agent.
    phone_number format: +1XXXXXXXXXX
    """
    settings = get_settings()
    headers = get_headers()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{RETELL_BASE_URL}/create-phone-number",
            headers=headers,
            json={
                "phone_number": phone_number,
                "phone_number_type": "twilio",
                "phone_number_pretty": phone_number,
                "inbound_agent_id": settings.RETELL_AGENT_ID,
                "outbound_agent_id": settings.RETELL_AGENT_ID,
                "area_code": int(phone_number[2:5]),
                "nickname": "RM-Ojas-US"
            }
        )
        return response.json()

async def get_all_phone_numbers() -> list:
    headers = get_headers()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{RETELL_BASE_URL}/list-phone-numbers",
            headers=headers
        )
        return response.json()

async def make_single_call(
    to_number: str,
    lead_name: str,
    business_name: str,
    lead_id: str,
    campaign_id: str
) -> dict:
    """Make one outbound call via Retell"""
    settings = get_settings()
    headers = get_headers()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{RETELL_BASE_URL}/create-phone-call",
            headers=headers,
            json={
                "from_number": settings.TWILIO_PHONE_NUMBER,
                "to_number": to_number,
                "override_agent_id": settings.RETELL_AGENT_ID,
                "retell_llm_dynamic_variables": {
                    "business_name": business_name,
                    "prospect_name": lead_name
                },
                "metadata": {
                    "lead_id": lead_id,          # webhook matches on this key
                    "campaign_id": campaign_id,
                    "lead_name": lead_name,
                    "business_name": business_name
                }
            }
        )
        return response.json()

async def register_webhook(webhook_url: str) -> dict:
    """
    Tell Retell where to send call events.
    Run once after deployment.
    """
    settings = get_settings()
    if not settings.RETELL_AGENT_ID:
        logger.error("Failed to register webhook: RETELL_AGENT_ID is not configured")
        return {"error": "RETELL_AGENT_ID is not configured"}
        
    try:
        from retell import Retell
        client = Retell(api_key=settings.RETELL_API_KEY)
        
        agent = client.agent.update(
            agent_id=settings.RETELL_AGENT_ID,
            webhook_url=webhook_url
        )
        logger.info("Successfully registered webhook with Retell", webhook_url=webhook_url)
        return {"agent_id": agent.agent_id, "webhook_url": agent.webhook_url}
    except Exception as e:
        logger.error("Failed to register webhook with Retell", error=str(e))
        return {"error": str(e)}

