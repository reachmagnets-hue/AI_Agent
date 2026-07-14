import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.utils.automations import send_outreach_email

async def main():
    email = "apofficial1405@gmail.com"
    print(f"Sending outreach email to {email}...")
    result = await send_outreach_email(
        to_email=email,
        to_name="AP Official",
        business_name="AP Ventures",
        business_type="Technology"
    )
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
