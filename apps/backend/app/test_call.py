import asyncio
import os
import sys
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Add parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.retell_service import RetellService
from app.utils.automations import send_appointment_email, send_appointment_sms, send_whatsapp_message
from app.utils.dnc import is_on_dnc_registry

async def main():
    print("🚀 Reach Magnets - AI Voice Agent calling & Follow-up Test Utility")
    print("=================================================================")
    
    # Check for target number
    if len(sys.argv) < 2:
        phone_number = input("Enter target phone number for test call (e.g. +1234567890): ").strip()
    else:
        phone_number = sys.argv[1]
        
    if not phone_number:
        print("❌ Phone number is required.")
        return

    name = input("Enter contact name [Default: Test Prospect]: ").strip() or "Test Prospect"
    email = input("Enter contact email [Default: test@example.com]: ").strip() or "test@example.com"
    
    print("\n--- Phase 0: DNC Registry Verification ---")
    on_dnc = await is_on_dnc_registry(phone_number)
    if on_dnc:
        print(f"⚠️ Warning: Phone number {phone_number} is registered on the FCC Do Not Call (DNC) Registry!")
        bypass = input("Do you want to bypass the DNC block for this test? (y/n) [Default: n]: ").strip().lower()
        if bypass != 'y':
            print("❌ Call blocked by DNC Compliance Guard. Exiting test.")
            return
        print("Bypassing DNC check for testing purposes...")
    else:
        print(f"✅ Number {phone_number} passed DNC compliance registry check.")
        
    print("\n--- Phase 1: Initiating Outbound Call ---")
    retell = RetellService()
    print(f"Retell Service Configured: {retell.is_configured()}")
    print(f"Initiating call to {name} at {phone_number}...")
    
    try:
        call_res = await retell.make_call(
            phone_number=phone_number,
            campaign_id="test-campaign-id",
            contact_id="test-contact-id"
        )
        print(f"✅ Call outcome: {call_res}")
    except Exception as e:
        print(f"❌ Failed to place call: {e}")
        print("Continuing to test follow-up automations anyway using mocked values...")

    print("\n--- Phase 2: Testing Follow-up Automations (SMS, Email, WhatsApp) ---")
    appointment_details = "Tomorrow at 3:00 PM EST (Marketing consultation & Reach Magnets services walk-through)"
    
    # 1. Test SMS (Twilio)
    print("\n[1/3] Sending Twilio SMS confirmation...")
    sms_ok = await send_appointment_sms(phone_number, name, appointment_details)
    if sms_ok:
        print("✅ SMS sent successfully (or mock processed).")
    else:
        print("❌ SMS failed.")
        
    # 2. Test Email (Brevo)
    print("\n[2/3] Sending Brevo Email confirmation...")
    email_ok = await send_appointment_email(email, name, appointment_details)
    if email_ok:
        print("✅ Email sent successfully (or mock processed).")
    else:
        print("❌ Email failed.")
        
    # 3. Test WhatsApp (Meta API / Link)
    print("\n[3/3] Sending WhatsApp follow-up details...")
    whatsapp_ok = await send_whatsapp_message(
        to_phone=phone_number,
        to_name=name,
        message_text=f"Your marketing consulting slot details: {appointment_details}"
    )
    if whatsapp_ok:
        print("✅ WhatsApp notification processed successfully.")
    else:
        print("❌ WhatsApp notification failed.")

    print("\n=================================================================")
    print("🎉 Test execution completed. Configure your credentials in .env to connect live services.")

if __name__ == "__main__":
    asyncio.run(main())
