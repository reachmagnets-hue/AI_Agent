import asyncio
import os
import sys

# Ensure backend path is in Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.utils.automations import render_outreach_email

def main():
    print("Generating outreach email previews...")
    
    # 1. Test General Niche
    subject_gen, html_gen = render_outreach_email(
        to_name="Alex",
        business_name="Vertex Consulting",
        business_type="Professional Services"
    )
    with open("test_general_email.html", "w", encoding="utf-8") as f:
        f.write(html_gen)
    print(f"General Email Generated. Subject: '{subject_gen}' -> Saved to test_general_email.html")
    
    # 2. Test Automotive Niche
    subject_auto, html_auto = render_outreach_email(
        to_name="Dave",
        business_name="Apex Auto Body",
        business_type="Automotive Repair"
    )
    with open("test_automotive_email.html", "w", encoding="utf-8") as f:
        f.write(html_auto)
    print(f"Automotive Email Generated. Subject: '{subject_auto}' -> Saved to test_automotive_email.html")

if __name__ == "__main__":
    main()
