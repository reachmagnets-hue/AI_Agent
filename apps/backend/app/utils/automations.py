import os
import structlog
import httpx
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# Try to import sib_api_v3_sdk for Brevo
try:
    import sib_api_v3_sdk
    from sib_api_v3_sdk.rest import ApiException
    BREVO_AVAILABLE = True
except ImportError:
    BREVO_AVAILABLE = False
    logger.warning("sib-api-v3-sdk not available. Brevo email sending will be mocked.")

# Try to import Twilio
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logger.warning("twilio SDK not available. SMS sending will be mocked.")


async def send_smtp_email_direct(to_email: str, subject: str, html_content: str) -> bool:
    """Send standard email via secure SMTP client connection"""
    settings = get_settings()
    host = settings.SMTP_HOST
    port = settings.SMTP_PORT
    user = settings.SMTP_USER
    password = settings.SMTP_PASSWORD
    sender = settings.SENDER_EMAIL or user
    sender_name = settings.SENDER_NAME or "Reach Magnets"

    logger.info("Triggering SMTP email direct dispatch", to=to_email, host=host, port=port)

    if not user or not password:
        logger.warning("SMTP user or password not configured. Mocking SMTP email delivery.")
        logger.info(f"Mock SMTP Email payload:\nTo: {to_email}\nSubject: {subject}\nBody preview: {html_content[:200]}...")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{sender_name} <{sender}>"
        msg["To"] = to_email

        msg.attach(MIMEText(html_content, "html"))

        import asyncio
        def sync_send():
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.starttls()
                server.login(user, password)
                server.sendmail(sender, to_email, msg.as_string())

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, sync_send)
        logger.info("SMTP email dispatched successfully", to=to_email)
        return True
    except Exception as e:
        logger.error("Failed to send email via SMTP", error=str(e))
        return False


async def send_appointment_email(to_email: str, to_name: str, appointment_details: str) -> bool:
    """Send appointment confirmation details via chosen Email Provider (Brevo or SMTP)"""
    settings = get_settings()
    sender_email = settings.SENDER_EMAIL
    sender_name = settings.SENDER_NAME

    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #6C5DD3;">Reach Magnets - Appointment Scheduled 📅</h2>
            <p>Hello <strong>{to_name}</strong>,</p>
            <p>We are excited to confirm your upcoming appointment with Reach Magnets!</p>
            <div style="background-color: #f7f7f7; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <p style="margin: 0;"><strong>Details:</strong></p>
                <p style="margin: 5px 0 0 0;">{appointment_details}</p>
            </div>
            <p>If you need to reschedule or have any questions, feel free to reply directly to this email or connect with us on WhatsApp.</p>
            <br>
            <p>Best regards,</p>
            <p><strong>Reach Magnets Team</strong></p>
        </body>
    </html>
    """

    if settings.EMAIL_PROVIDER == "smtp":
        return await send_smtp_email_direct(to_email, "Your Reach Magnets Appointment Details", html_content)

    api_key = settings.BREVO_API_KEY
    logger.info("Triggering Brevo appointment email", to_email=to_email, to_name=to_name)

    if not BREVO_AVAILABLE or not api_key or api_key == "your_brevo_api_key":
        logger.warning("Brevo email not configured. Mocking email delivery.")
        return True

    try:
        # Configure API key authorization
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = api_key

        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
        
        sender = {"name": sender_name, "email": sender_email}
        to = [{"email": to_email, "name": to_name}]
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #6C5DD3;">Reach Magnets - Appointment Scheduled 📅</h2>
                <p>Hello <strong>{to_name}</strong>,</p>
                <p>We are excited to confirm your upcoming appointment with Reach Magnets!</p>
                <div style="background-color: #f7f7f7; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <p style="margin: 0;"><strong>Details:</strong></p>
                    <p style="margin: 5px 0 0 0;">{appointment_details}</p>
                </div>
                <p>If you need to reschedule or have any questions, feel free to reply directly to this email or connect with us on WhatsApp.</p>
                <br>
                <p>Best regards,</p>
                <p><strong>Reach Magnets Team</strong></p>
            </body>
        </html>
        """
        
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            sender=sender,
            to=to,
            subject="Your Reach Magnets Appointment Details",
            html_content=html_content
        )

        api_response = api_instance.send_transac_email(send_smtp_email)
        logger.info("Brevo email sent successfully", message_id=api_response.message_id)
        return True
    except ApiException as e:
        logger.error("Exception when calling TransactionalEmailsApi->send_transac_email", error=str(e))
        return False
    except Exception as e:
        logger.error("Error sending Brevo email", error=str(e))
        return False


async def send_appointment_sms(to_phone: str, to_name: str, appointment_details: str) -> bool:
    """Send appointment details SMS via Twilio"""
    settings = get_settings()
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_phone = settings.TWILIO_PHONE_NUMBER

    logger.info("Triggering appointment SMS", to_phone=to_phone, to_name=to_name)

    if not TWILIO_AVAILABLE or not account_sid or account_sid == "your_twilio_account_sid":
        logger.warning("Twilio SMS not configured. Mocking SMS delivery.")
        return True

    try:
        client = TwilioClient(account_sid, auth_token)
        message_body = (
            f"Hello {to_name}, your Reach Magnets appointment has been successfully scheduled! "
            f"Details: {appointment_details}. Reply to this text if you have questions."
        )
        
        message = client.messages.create(
            body=message_body,
            from_=from_phone,
            to=to_phone
        )
        logger.info("Twilio SMS sent successfully", message_sid=message.sid)
        return True
    except Exception as e:
        logger.error("Error sending Twilio SMS", error=str(e))
        return False


async def send_whatsapp_message(to_phone: str, to_name: str, message_text: str) -> bool:
    """Send WhatsApp message with click-to-chat options"""
    settings = get_settings()
    whatsapp_url = settings.WHATSAPP_API_URL
    token = settings.WHATSAPP_TOKEN

    logger.info("Triggering WhatsApp message", to_phone=to_phone, to_name=to_name)

    # Clean phone number (WhatsApp needs digits only, with country code)
    clean_phone = "".join(filter(str.isdigit, to_phone))
    if not clean_phone.startswith("+") and len(clean_phone) > 0:
        # Standard fallback for routing
        pass

    # Standard fallback link generation
    # For instant support, we can use wa.me links
    whatsapp_chat_link = f"https://wa.me/919999999999?text=Hi,%20I'm%20interested%20in%20Reach%20Magnets%20services!"

    if not whatsapp_url or not token or whatsapp_url == "your_whatsapp_api_url":
        logger.warning("WhatsApp API not configured. Mocking WhatsApp notification.")
        logger.info(f"Generated Click-to-Chat WhatsApp Link: {whatsapp_chat_link}")
        return True

    try:
        # Check if using Meta Cloud API or Evolution API by inspecting structure
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Meta Cloud API standard JSON payload
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "text",
            "text": {
                "preview_url": True,
                "body": f"Hello {to_name}, {message_text}\n\nWant to chat with our marketing specialists directly on WhatsApp? Click here: {whatsapp_chat_link}"
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(whatsapp_url, headers=headers, json=payload, timeout=10.0)
            if response.status_code in [200, 201]:
                logger.info("WhatsApp message sent successfully via API")
                return True
            else:
                logger.error("WhatsApp API returned error", status_code=response.status_code, body=response.text)
                return False
    except Exception as e:
        logger.error("Error sending WhatsApp message via API", error=str(e))
        return False


def render_outreach_email(to_name: str, business_name: Optional[str] = None, business_type: Optional[str] = None) -> tuple[str, str]:
    """
    Render outreach email body and subject based on the lead's niche (business_type).
    Returns (subject, html_content).
    """
    settings = get_settings()
    event_type_id = settings.CALCOM_EVENT_TYPE_ID or "5752986"
    booking_url = f"https://cal.com/reachmagnets/{event_type_id}"
    
    biz_name_str = business_name.strip() if business_name else ""
    
    # Niche classification
    is_automotive = False
    if business_type:
        bt_lower = business_type.lower()
        auto_keywords = ["automotive", "car", "dealer", "repair", "auto", "mechanic", "tire", "garage", "collision", "service center"]
        if any(kw in bt_lower for kw in auto_keywords):
            is_automotive = True

    if is_automotive:
        subject = f"A humble perspective on {biz_name_str}'s local visibility gaps" if biz_name_str else "A humble perspective on your local visibility gaps"
        business_phrase = biz_name_str if biz_name_str else "your business"
        
        body_content = f"""
        <p style="margin-top: 0; margin-bottom: 16px;">Hi {to_name},</p>
        
        <p style="margin-bottom: 16px;">Most auto shops and dealerships are losing valuable service bookings and sales every single day—not because their service isn't great, but because of small, fixable gaps in their online visibility.</p>
        
        <p style="margin-bottom: 16px;">We often see: a slow-loading mobile site (crucial when drivers are stranded or looking for quick service), low visibility on local maps (missing queries like "car repair near me"), or missing out entirely when potential customers search on ChatGPT/Gemini for "best mechanic near me" (Generative Engine Optimization/GEO).</p>
        
        <p style="margin-bottom: 16px;">The tricky part? Most shop owners are too busy keeping cars on the road to even notice these gaps exist.</p>
        
        <p style="margin-bottom: 16px;">At <strong>Reach Magnets</strong>, we've helped over 1,000 local businesses generate 2 million+ leads through strategic local SEO, AEO/GEO optimization, high-converting websites, and performance marketing—often increasing bookings and site traffic by 20%+ within months.</p>
        
        <p style="margin-bottom: 16px;">We would love to offer {business_phrase} a completely free, no-pressure digital marketing audit. Here is what you'll get:</p>
        
        <table border="0" cellpadding="0" cellspacing="0" style="margin: 20px 0; padding-left: 10px;">
            <tr>
                <td valign="top" style="padding-right: 10px; color: #6C5DD3; font-weight: bold; font-size: 18px; line-height: 1;">•</td>
                <td style="padding-bottom: 10px; font-size: 14.5px; color: #4b5563;"><strong>Local Map Ranking Check:</strong> How you rank in search results for direct repair and service keywords.</td>
            </tr>
            <tr>
                <td valign="top" style="padding-right: 10px; color: #6C5DD3; font-weight: bold; font-size: 18px; line-height: 1;">•</td>
                <td style="padding-bottom: 10px; font-size: 14.5px; color: #4b5563;"><strong>AI Visibility (GEO/AEO) Assessment:</strong> What smart assistants recommend when drivers ask for auto service options in your city.</td>
            </tr>
            <tr>
                <td valign="top" style="padding-right: 10px; color: #6C5DD3; font-weight: bold; font-size: 18px; line-height: 1;">•</td>
                <td style="padding-bottom: 10px; font-size: 14.5px; color: #4b5563;"><strong>Actionable Fixes:</strong> Specific speed and user experience improvements for your website to prevent booking abandonment.</td>
            </tr>
            <tr>
                <td valign="top" style="padding-right: 10px; color: #6C5DD3; font-weight: bold; font-size: 18px; line-height: 1;">•</td>
                <td style="padding-bottom: 10px; font-size: 14.5px; color: #4b5563;"><strong>Competitor Insights:</strong> A quick look at what other local shops are doing to capture leads.</td>
            </tr>
            <tr>
                <td valign="top" style="padding-right: 10px; color: #6C5DD3; font-weight: bold; font-size: 18px; line-height: 1;">•</td>
                <td style="padding-bottom: 0; font-size: 14.5px; color: #4b5563;"><strong>Growth Roadmap:</strong> A step-by-step plan to scale your local reach, leads, and service revenue.</td>
            </tr>
        </table>
        
        <p style="margin-bottom: 24px;">It takes only about 30 minutes, but it could easily save you months of slow bookings and thousands in trial-and-error marketing spend.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <!--[if mso]>
            <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word" href="{booking_url}" style="height:48px;v-text-anchor:middle;width:240px;" arcsize="17%" stroke="f" fillcolor="#6C5DD3">
              <w:anchorlock/>
              <center style="color:#ffffff;font-family:sans-serif;font-size:15px;font-weight:bold;">Claim My Free Audit →</center>
            </v:roundrect>
            <![endif]-->
            <a href="{booking_url}" style="background-color: #6C5DD3; color: #ffffff; display: inline-block; font-family: sans-serif; font-size: 15px; font-weight: bold; line-height: 48px; text-align: center; text-decoration: none; width: 240px; -webkit-text-size-adjust: none; mso-hide: all; border-radius: 8px; box-shadow: 0 4px 12px rgba(108, 93, 211, 0.25);">Claim My Free Audit &rarr;</a>
        </div>
        
        <p style="margin-bottom: 0;">Looking forward to helping you uncover new growth opportunities.</p>
        """
    else:
        # General Niche template (Humble & human fallback)
        subject = f"A humble perspective on {biz_name_str}'s marketing gaps" if biz_name_str else "A humble perspective on your marketing gaps"
        business_phrase = biz_name_str if biz_name_str else "your business"
        
        body_content = f"""
        <p style="margin-top: 0; margin-bottom: 16px;">Hi {to_name},</p>
        
        <p style="margin-bottom: 16px;">Most businesses are losing leads every single day, not because their product or service isn't good enough, but because of small, fixable gaps in their marketing: a slow website, poor search visibility, weak SEO, missed GEO (Generative Engine Optimization) opportunities, ineffective AEO (Answer Engine Optimization), collaborative performance marketing campaigns that aren't delivering results, or social media that isn't bringing in real engagement.</p>
        
        <p style="margin-bottom: 16px;">The tricky part? Most businesses don't even know these gaps exist until someone points them out.</p>
        
        <p style="margin-bottom: 16px;">At <strong>Reach Magnets</strong>, we've helped over 1,000 businesses generate 2 million+ leads through strategic SEO, GEO, AEO, collaborative performance marketing, social media management, and high-converting website solutions, often increasing traffic by 20%+ within months.</p>
        
        <p style="margin-bottom: 16px;">We'd like to offer {business_phrase} a completely free marketing audit, no strings attached. Here's what you'll get:</p>
        
        <table border="0" cellpadding="0" cellspacing="0" style="margin: 20px 0; padding-left: 10px;">
            <tr>
                <td valign="top" style="padding-right: 10px; color: #6C5DD3; font-weight: bold; font-size: 18px; line-height: 1;">•</td>
                <td style="padding-bottom: 10px; font-size: 14.5px; color: #4b5563;"><strong>A clear breakdown:</strong> How your marketing is performing right now.</td>
            </tr>
            <tr>
                <td valign="top" style="padding-right: 10px; color: #6C5DD3; font-weight: bold; font-size: 18px; line-height: 1;">•</td>
                <td style="padding-bottom: 10px; font-size: 14.5px; color: #4b5563;"><strong>An SEO, GEO, and AEO visibility assessment:</strong> Identifying missed search and AI opportunities.</td>
            </tr>
            <tr>
                <td valign="top" style="padding-right: 10px; color: #6C5DD3; font-weight: bold; font-size: 18px; line-height: 1;">•</td>
                <td style="padding-bottom: 10px; font-size: 14.5px; color: #4b5563;"><strong>Actionable Fixes:</strong> Specific improvements to start seeing results faster.</td>
            </tr>
            <tr>
                <td valign="top" style="padding-right: 10px; color: #6C5DD3; font-weight: bold; font-size: 18px; line-height: 1;">•</td>
                <td style="padding-bottom: 10px; font-size: 14.5px; color: #4b5563;"><strong>Competitor Insights:</strong> Insights into what is working for your direct competitors.</td>
            </tr>
            <tr>
                <td valign="top" style="padding-right: 10px; color: #6C5DD3; font-weight: bold; font-size: 18px; line-height: 1;">•</td>
                <td style="padding-bottom: 0; font-size: 14.5px; color: #4b5563;"><strong>A custom roadmap:</strong> A structured path to grow your reach, leads, and revenue.</td>
            </tr>
        </table>
        
        <p style="margin-bottom: 24px;">In just 30 minutes, you'll gain valuable insights that could save you months of trial and error and thousands in wasted marketing spend.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <!--[if mso]>
            <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word" href="{booking_url}" style="height:48px;v-text-anchor:middle;width:240px;" arcsize="17%" stroke="f" fillcolor="#6C5DD3">
              <w:anchorlock/>
              <center style="color:#ffffff;font-family:sans-serif;font-size:15px;font-weight:bold;">Claim My Free Audit →</center>
            </v:roundrect>
            <![endif]-->
            <a href="{booking_url}" style="background-color: #6C5DD3; color: #ffffff; display: inline-block; font-family: sans-serif; font-size: 15px; font-weight: bold; line-height: 48px; text-align: center; text-decoration: none; width: 240px; -webkit-text-size-adjust: none; mso-hide: all; border-radius: 8px; box-shadow: 0 4px 12px rgba(108, 93, 211, 0.25);">Claim My Free Audit &rarr;</a>
        </div>
        
        <p style="margin-bottom: 0;">Looking forward to helping you uncover new growth opportunities.</p>
        """

    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f9fafb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; color: #1f2937;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f9fafb; padding: 20px 0;">
        <tr>
            <td align="center">
                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03); overflow: hidden;">
                    <!-- Accent Bar -->
                    <tr>
                        <td height="6" style="background-color: #6C5DD3; line-height: 6px; font-size: 6px;">&nbsp;</td>
                    </tr>
                    <!-- Header -->
                    <tr>
                        <td style="padding: 32px 32px 20px 32px; text-align: center;">
                            <h1 style="color: #6C5DD3; font-size: 26px; font-weight: 800; margin: 0; letter-spacing: -0.5px;">Reach Magnets</h1>
                            <p style="color: #6b7280; font-size: 13px; font-weight: 500; text-transform: uppercase; letter-spacing: 1px; margin: 6px 0 0 0;">Customer Acquisition & Online Visibility</p>
                        </td>
                    </tr>
                    <!-- Divider -->
                    <tr>
                        <td style="padding: 0 32px;">
                            <hr style="border: 0; border-top: 1px solid #f3f4f6; margin: 0;">
                        </td>
                    </tr>
                    <!-- Body Content -->
                    <tr>
                        <td style="padding: 32px; font-size: 15px; line-height: 1.625; color: #374151;">
                            {body_content}
                        </td>
                    </tr>
                    <!-- Divider -->
                    <tr>
                        <td style="padding: 0 32px;">
                            <hr style="border: 0; border-top: 1px solid #f3f4f6; margin: 0;">
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 32px 32px 32px; text-align: center; background-color: #fafbfe;">
                            <p style="font-size: 12px; color: #9ca3af; margin: 0 0 8px 0; line-height: 1.5;">
                                &copy; 2026 Reach Magnets &bull; Digital Marketing Excellence
                            </p>
                            <p style="font-size: 11px; color: #cbd5e1; margin: 0; line-height: 1.4;">
                                If you prefer not to receive helpful audits from us, you can reply "stop" to unsubscribe.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    return subject, full_html


async def send_outreach_email(to_email: str, to_name: str, business_name: Optional[str] = None, business_type: Optional[str] = None) -> bool:
    """Send initial approach/outreach email introducing services via chosen Email Provider (Brevo or SMTP)"""
    settings = get_settings()
    sender_email = settings.SENDER_EMAIL
    sender_name = settings.SENDER_NAME

    subject, html_content = render_outreach_email(to_name, business_name, business_type)

    if settings.EMAIL_PROVIDER == "smtp":
        return await send_smtp_email_direct(to_email, subject, html_content)

    api_key = settings.BREVO_API_KEY
    logger.info("Triggering Brevo outreach email", to_email=to_email, to_name=to_name)

    if not BREVO_AVAILABLE or not api_key or api_key == "your_brevo_api_key":
        logger.warning("Brevo email not configured. Mocking outreach email delivery.")
        return True

    try:
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = api_key

        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
        
        sender = {"name": sender_name, "email": sender_email}
        to = [{"email": to_email, "name": to_name}]
        
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            sender=sender,
            to=to,
            subject=subject,
            html_content=html_content
        )

        api_response = api_instance.send_transac_email(send_smtp_email)
        logger.info("Brevo outreach email sent successfully", message_id=api_response.message_id)
        return True
    except ApiException as e:
        logger.error("Exception when calling TransactionalEmailsApi->send_transac_email for outreach", error=str(e))
        return False
    except Exception as e:
        logger.error("Error sending Brevo outreach email", error=str(e))
        return False


async def send_outreach_sms(to_phone: str, to_name: str, business_name: Optional[str] = None) -> bool:
    """Send initial approach/outreach SMS introducing services via Twilio"""
    settings = get_settings()
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_phone = settings.TWILIO_PHONE_NUMBER

    logger.info("Triggering outreach SMS", to_phone=to_phone, to_name=to_name)

    if not TWILIO_AVAILABLE or not account_sid or account_sid == "your_twilio_account_sid":
        logger.warning("Twilio SMS not configured. Mocking outreach SMS delivery.")
        return True

    try:
        client = TwilioClient(account_sid, auth_token)
        biz_str = f" for {business_name}" if business_name else ""
        message_body = (
            f"Hi {to_name}! This is Sarah from Reach Magnets. "
            f"We help businesses{biz_str} get more customers online using SEO, Ads, and custom websites. "
            f"I'm giving you a quick call right now to offer a free 15-min digital marketing audit. Hope to speak soon!"
        )
        
        message = client.messages.create(
            body=message_body,
            from_=from_phone,
            to=to_phone
        )
        logger.info("Twilio outreach SMS sent successfully", message_sid=message.sid)
        return True
    except Exception as e:
        logger.error("Error sending Twilio outreach SMS", error=str(e))
        return False

