import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'reachmagnets.db')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

indexes = [
    "CREATE INDEX IF NOT EXISTS idx_calls_created_at ON calls(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_calls_outcome ON calls(outcome)",
    "CREATE INDEX IF NOT EXISTS idx_calls_status ON calls(status)",
    "CREATE INDEX IF NOT EXISTS idx_leads_campaign_id ON leads(campaign_id)",
    "CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)",
    "CREATE INDEX IF NOT EXISTS idx_appointments_meeting_date ON appointments(meeting_date)"
]

for idx in indexes:
    print(f"Executing: {idx}")
    cursor.execute(idx)

conn.commit()
conn.close()
print("Indexes added successfully!")
