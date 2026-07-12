import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.call import Call
from app.models.lead import Lead

def list_picked_calls():
    db = SessionLocal()
    try:
        # Fetch calls that have transcripts (meaning they were picked up)
        calls = db.query(Call).filter(Call.transcript.isnot(None), Call.transcript != "").order_by(Call.created_at.desc()).all()
        
        if not calls:
            print("No picked calls with transcripts found in the database.")
            return

        print(f"Found {len(calls)} call(s) in the database that were picked up and have transcripts:\n")
        print("=" * 80)
        
        for idx, call in enumerate(calls, 1):
            lead_name = call.lead.full_name if call.lead else "Unknown Lead"
            to_num = call.to_number or (call.lead.phone if call.lead else "N/A")
            
            print(f"#{idx} Call Details:")
            print(f"  Prospect Name: {lead_name}")
            print(f"  Phone Number : {to_num}")
            print(f"  Call Date    : {call.created_at}")
            print(f"  Status       : {call.status}")
            print(f"  Outcome      : {call.outcome}")
            print(f"  Duration     : {call.duration_seconds} seconds")
            print("\n  TRANSCRIPT:")
            print("-" * 50)
            lines = call.transcript.strip().split("\n")
            for line in lines:
                print(f"    {line}")
            print("-" * 50)
            print("=" * 80)
            
    except Exception as e:
        print(f"Error querying database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    list_picked_calls()
