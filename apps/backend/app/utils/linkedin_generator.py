from google import genai
import structlog
from app.core.config import get_settings

logger = structlog.get_logger(__name__)

async def generate_linkedin_message(full_name: str, business_name: str, business_type: str) -> str:
    """
    Generate a highly personalized connection invitation message using Gemini 2.5 Flash.
    Strictly capped at 290 characters to fit within LinkedIn connection limits.
    """
    settings = get_settings()
    api_key = settings.GEMINI_API_KEY

    # Default fallback message if Gemini is unconfigured or fails
    fallback_message = f"Hi {full_name or 'there'}, noticed your work in {business_type or 'marketing'} at {business_name or 'your company'}. Let's connect!"

    if not api_key:
        logger.warning("GEMINI_API_KEY not configured. Returning fallback message.")
        return fallback_message

    try:
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        You are a warm, professional, and consultative outreach assistant.
        Write a personalized, conversational, and non-pushy LinkedIn connection request invitation.
        
        Prospect Info:
        - Name: {full_name or "Prospect"}
        - Company: {business_name or "their company"}
        - Industry: {business_type or "their industry"}
        
        CRITICAL RULES:
        1. Keep the entire response under 280 characters.
        2. Speak conversationally.
        3. Do not use generic sales pitches or hashtags.
        4. Focus on connecting, learning about their business challenges, and growing together.
        5. Output ONLY the invitation message itself. Do not include any intros, subject lines, or quotes.
        """
        
        # Run blocking genai call in executor
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: client.models.generate_content(model="gemini-2.5-flash", contents=prompt))
        
        text = response.text.strip() if response and response.text else fallback_message
        
        # Enforce character limit safety
        if len(text) > 295:
            text = text[:290] + "..."
            
        logger.info("LinkedIn message generated successfully with Gemini", len=len(text))
        return text
    except Exception as e:
        logger.error("Error generating LinkedIn message with Gemini", error=str(e))
        return fallback_message
