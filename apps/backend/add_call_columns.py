import sqlite3

conn = sqlite3.connect('reachmagnets.db')
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE calls ADD COLUMN objection_raised VARCHAR(250)")
except sqlite3.OperationalError as e:
    print(f"objection_raised: {e}")

conn.commit()
conn.close()
print("Migration completed.")
