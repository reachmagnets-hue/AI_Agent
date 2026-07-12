import sqlite3

conn = sqlite3.connect('reachmagnets.db')
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE leads ADD COLUMN zip_code VARCHAR(20)")
    print("zip_code column added successfully.")
except sqlite3.OperationalError as e:
    print(f"zip_code: {e}")

conn.commit()
conn.close()
print("Migration completed.")
