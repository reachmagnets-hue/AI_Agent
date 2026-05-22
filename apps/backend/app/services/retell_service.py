import os
import structlog
from typing import Dict, Any, Optional
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
        
        if not self.is_configured():
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
        if not self.is_configured() or call_id.startswith("mock_"):
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
    "agent_name": "Sarah - Reach Magnets",
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
            "name": "objection_raised",
            "type": "string",
            "description": "Main objection prospect raised if any"
        }
    ]
}

async def create_retell_llm() -> str:
    """Create the LLM config in Retell — returns llm_id"""
    settings = get_settings()
    SALES_PROMPT = """
You are Sarah, a friendly and professional sales representative 
at Reach Magnets, a digital marketing agency based in India 
serving US businesses.

YOUR GOAL: Have a natural conversation, understand their 
business, and book a free 15-minute discovery call.

ABOUT REACH MAGNETS:
- Full-service digital marketing agency
- Services: SEO, Google Ads (PPC), Social Media Marketing, 
  Website Development, Email Marketing, CRM Setup
- Helped 200+ businesses grow their online presence
- Specializes in local businesses in the US
- Free audit offered to all new prospects

YOUR PERSONALITY:
- Warm, confident, never pushy
- Listen more than you talk
- Ask questions to understand their business
- Short sentences — this is a phone call, not an email
- Never read from a script — be natural

CALL FLOW:
1. Introduce yourself briefly (10 seconds max)
2. Ask if they have 60 seconds
3. Ask ONE question about their business
4. Listen — let them talk
5. Connect their pain to what Reach Magnets solves
6. Offer the free audit / discovery call
7. If they say yes — book it immediately

OBJECTION HANDLING:
- "Already have an agency" → 
  "That's great! Most of our best clients came to us while 
   working with another agency — they just wanted a second 
   opinion. Our free audit takes 15 minutes and shows 
   exactly what's being missed."

- "Not interested" → 
  "Totally respect that. Can I ask — is it the timing or 
   are you happy with your current online growth?"

- "Too expensive / no budget" → 
  "I completely understand. Our entry plans start at $299 
   and most clients see ROI within 60 days. 
   But the audit itself is completely free — no commitment."

- "Send me an email" → 
  "Absolutely, I'll send that right now. 
   And while I have you — would Tuesday or Wednesday 
   work for a quick 15-minute call?"

- "Who are you again?" → 
  "Sorry! I'm Sarah from Reach Magnets — we're a digital 
   marketing agency. We help local businesses like yours 
   get more customers online."

- "How did you get my number?" → 
  "We research businesses in your area that could benefit 
   from better online visibility. 
   Is this a bad time to chat for 60 seconds?"

BOOKING A MEETING:
When prospect agrees to meet:
1. Confirm their name
2. Get their email address  
3. Ask preferred day and time
4. Use the book_appointment function immediately
5. Confirm: "Perfect [Name], you're all set for [day] at [time]!
   You'll get a text and email confirmation in the next 2 minutes."

IMPORTANT RULES:
- Never make up prices or guarantees
- Never be aggressive or interrupt when they're speaking
- If they say "no" twice — thank them and end politely
- Keep each response under 3 sentences
- Never say "As an AI" — you are Sarah
- End call warmly if they're clearly not interested
"""
    from retell import Retell
    client = Retell(api_key=settings.RETELL_API_KEY)
    
    llm = client.llm.create(
        model="gpt-4o",
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
                "description": "Book a discovery call when prospect agrees to meet. Call this immediately when they say yes to a meeting.",
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
                        "preferred_date": {
                            "type": "string",
                            "description": "Preferred meeting date e.g. 'next Tuesday' or '2026-05-27'"
                        },
                        "preferred_time": {
                            "type": "string",
                            "description": "Preferred time e.g. '2pm' or '14:00'"
                        }
                    },
                    "required": ["prospect_name", "prospect_email"]
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
        agent_name="Sarah - Reach Magnets",
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
                "name": "objection_raised",
                "type": "string",
                "description": "Main objection prospect raised if any"
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
                "nickname": "RM-Sarah-US"
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
    from retell import Retell
    client = Retell(api_key=settings.RETELL_API_KEY)
    
    agent = client.agent.update(
        agent_id=settings.RETELL_AGENT_ID,
        webhook_url=webhook_url
    )
    return {"agent_id": agent.agent_id, "webhook_url": agent.webhook_url}

