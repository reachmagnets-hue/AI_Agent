import json
import structlog
from typing import Dict, Any, Optional
from google import genai
from google.genai import types
from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# Define the JSON schema for Gemini to strictly extract outcomes
OUTCOME_SCHEMA = {
    "type": "object",
    "properties": {
        "classification": {
            "type": "string",
            "enum": ["meeting_booked", "interested", "not_interested", "neutral_reply", "spam"],
            "description": "Classify the prospect's reply intent."
        },
        "meeting_date": {
            "type": "string",
            "description": "If meeting_booked, extract the date in YYYY-MM-DD format. E.g., '2023-11-20'. If not provided, output null.",
            "nullable": True
        },
        "meeting_time": {
            "type": "string",
            "description": "If meeting_booked, extract the time in HH:MM AM/PM format. E.g., '02:00 PM'. If not provided, output null.",
            "nullable": True
        },
        "meeting_timezone": {
            "type": "string",
            "description": "If meeting_booked, extract the timezone if mentioned. E.g., 'EST'. If not provided, output null.",
            "nullable": True
        },
        "summary": {
            "type": "string",
            "description": "A 1-2 sentence summary of what the prospect said."
        }
    },
    "required": ["classification", "summary"]
}

SYSTEM_PROMPT = """
You are an expert AI Sales Assistant. Your job is to review a conversation between our sales team and a prospect.
You must analyze the PROSPECT'S replies and determine the outcome of the conversation.

If the prospect agreed to a meeting/call and provided or agreed to a specific time, classify as 'meeting_booked' and extract the date/time.
If the prospect asks for more information or says "sure, send me details", classify as 'interested'.
If the prospect says "no thanks", "unsubscribe", or "not a fit", classify as 'not_interested'.

Be extremely precise. Only output the requested JSON schema.
"""

async def analyze_inbox_message(conversation_history: str) -> Dict[str, Any]:
    """
    Passes a conversation thread to Gemini to determine the outcome.
    Returns a dictionary matching OUTCOME_SCHEMA.
    """
    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is missing. Cannot run Inbox Review.")
        return {"classification": "neutral_reply", "summary": "API Key missing."}

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    prompt = f"Analyze the following conversation thread:\n\n{conversation_history}"
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=OUTCOME_SCHEMA,
                system_instruction=SYSTEM_PROMPT,
                temperature=0.1
            )
        )
        
        if not response.text:
            return {"classification": "neutral_reply", "summary": "Empty response from AI."}
            
        data = json.loads(response.text)
        return data
        
    except Exception as e:
        logger.error("Error analyzing message with Gemini", error=str(e))
        return {"classification": "neutral_reply", "summary": f"Error parsing AI response: {str(e)}"}
