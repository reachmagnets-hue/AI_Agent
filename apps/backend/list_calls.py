import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.call import Call
from app.models.lead import Lead

def list_all_calls():
    db = SessionLocal()
    try:
        calls = db.query(Call).order_by(Call.created_at.desc()).all()
        if not calls:
            print("No calls found in the database.")
            return

        print(f"Found {len(calls)} call records in the database:\n")
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
            
            if call.transcript:
                print("\n  TRANSCRIPT:")
                print("-" * 50)
                # Indent transcript lines
                lines = call.transcript.strip().split("\n")
                for line in lines:
                    print(f"    {line}")
                print("-" * 50)
            else:
                print("  TRANSCRIPT   : None (Call not picked up / No conversation)")
                
            print("=" * 80)
            
    except Exception as e:
        print(f"Error querying database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    list_all_calls()
