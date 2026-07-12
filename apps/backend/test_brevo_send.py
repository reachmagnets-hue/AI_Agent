import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.utils.automations import send_outreach_email

async def main():
    emails = ["chetupatil605@gmail.com", "harshfulara51@gmail.com"]
    for email in emails:
        print(f"Sending test outreach email to {email}...")
        result = await send_outreach_email(
            to_email=email,
            to_name="Chetan",
            business_name="Vertex Consulting",
            business_type="Consulting"
        )
        print(f"Result for {email}: {result}")

if __name__ == "__main__":
    asyncio.run(main())
