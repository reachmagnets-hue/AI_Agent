import sqlite3

conn = sqlite3.connect('reachmagnets.db')
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE leads ADD COLUMN linkedin_url VARCHAR(300)")
except sqlite3.OperationalError as e:
    print(f"linkedin_url: {e}")

try:
    cursor.execute("ALTER TABLE leads ADD COLUMN linkedin_message TEXT")
except sqlite3.OperationalError as e:
    print(f"linkedin_message: {e}")

try:
    cursor.execute("ALTER TABLE leads ADD COLUMN linkedin_sent_at DATETIME")
except sqlite3.OperationalError as e:
    print(f"linkedin_sent_at: {e}")

conn.commit()
conn.close()
print("Migration completed.")
