from google import genai
import structlog
from app.core.config import get_settings

logger = structlog.get_logger(__name__)

async def generate_linkedin_message(full_name: str, business_name: str, business_type: str) -> str:
    """
    Generate a highly personalized LinkedIn message based on the user's detailed introducing template.
    Uses Gemini 2.5 Flash for smart personalization if configured.
    """
    settings = get_settings()
    api_key = settings.GEMINI_API_KEY

    first_name = full_name.split()[0] if full_name else "there"
    biz_name = business_name.strip() if business_name else "your company"
    ind_name = business_type.strip() if business_type else "your industry"

    fallback_message = (
        f"Hi {first_name},\n\n"
        f"I hope you're doing well.\n\n"
        f"I wanted to reach out and introduce myself and Reach Magnets.\n\n"
        f"We founded Reach Magnets with a clear mission: to help businesses build a stronger digital presence and "
        f"create a predictable system for generating leads and acquiring customers online. Over the years, we've "
        f"seen many businesses invest heavily in marketing without having a strategy that consistently delivers "
        f"measurable results. That's where we focus our efforts.\n\n"
        f"Our team works with businesses to improve their online visibility, generate qualified leads, and increase "
        f"conversions through a combination of SEO, performance marketing, website optimization, social media marketing, "
        f"and conversion-focused digital strategies. Rather than treating each service as a separate activity, we focus "
        f"on creating a complete growth ecosystem that supports long-term business objectives.\n\n"
        f"What sets us apart is our emphasis on measurable outcomes. Whether it's improving search rankings, "
        f"increasing lead volume, optimizing advertising campaigns, or enhancing website performance, every "
        f"strategy we implement is designed to contribute directly to business growth.\n\n"
        f"While researching companies in {ind_name}, I came across your profile and was impressed by what "
        f"you've built at {biz_name}. I believe there may be opportunities to further strengthen your digital "
        f"presence and uncover additional channels for customer acquisition.\n\n"
        f"I'd be interested in learning more about your business, understanding your current growth initiatives, "
        f"and exchanging insights on what's working in today's market.\n\n"
        f"Looking forward to connecting.\n\n"
        f"Thank You!"
    )

    if not api_key:
        logger.warning("GEMINI_API_KEY not configured. Returning fallback template message.")
        return fallback_message

    try:
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        You are a warm, professional, and consultative outreach assistant.
        Write a personalized, conversational, and non-pushy LinkedIn message using this exact baseline template structure.
        
        Prospect Info:
        - First Name: {first_name}
        - Company: {biz_name}
        - Industry: {ind_name}
        
        Baseline Template:
        "Hi {first_name},
        
        I hope you're doing well.
        
        I wanted to reach out and introduce myself and Reach Magnets.
        
        We founded Reach Magnets with a clear mission: to help businesses build a stronger digital presence and create a predictable system for generating leads and acquiring customers online. Over the years, we've seen many businesses invest heavily in marketing without having a strategy that consistently delivers measurable results. That's where we focus our efforts.
        
        Our team works with businesses to improve their online visibility, generate qualified leads, and increase conversions through a combination of SEO, performance marketing, website optimization, social media marketing, and conversion-focused digital strategies. Rather than treating each service as a separate activity, we focus on creating a complete growth ecosystem that supports long-term business objectives.
        
        What sets us apart is our emphasis on measurable outcomes. Whether it's improving search rankings, increasing lead volume, optimizing advertising campaigns, or enhancing website performance, every strategy we implement is designed to contribute directly to business growth.
        
        While researching companies in [Industry], I came across your profile and was impressed by what you've built at [Company]. I believe there may be opportunities to further strengthen your digital presence and uncover additional channels for customer acquisition.
        
        I'd be interested in learning more about your business, understanding your current growth initiatives, and exchanging insights on what's working in today's market.
        
        Looking forward to connecting.
        
        Thank You!"
        
        CRITICAL RULES:
        1. Keep the exact paragraphs, flow, and tone of the template. Do not summarize or shorten it significantly.
        2. Replace '[First Name]' or similar placeholder with '{first_name}'.
        3. Replace '[Company]' or similar placeholder with '{biz_name}'.
        4. Replace '[Industry]' or similar placeholder with '{ind_name}'.
        5. You can slightly customize the phrasing in the fourth paragraph to sound natural and human, referencing their specific company or industry details.
        6. Do not include any subject lines, intros, notes, or quotes. Output ONLY the message text itself.
        """
        
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: client.models.generate_content(model="gemini-2.5-flash", contents=prompt))
        
        text = response.text.strip() if response and response.text else fallback_message
        
        # Enforce maximum safety length of 4000 characters (no short truncation)
        if len(text) > 4000:
            text = text[:3990] + "..."
            
        logger.info("LinkedIn message generated successfully with Gemini", len=len(text))
        return text
    except Exception as e:
        logger.error("Error generating LinkedIn message with Gemini", error=str(e))
        return fallback_message
