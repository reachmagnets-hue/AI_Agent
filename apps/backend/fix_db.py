import sqlite3

def fix_db():
    conn = sqlite3.connect('reachmagnets.db')
    cursor = conn.cursor()
    
    # Get columns in leads table
    cursor.execute("PRAGMA table_info(leads)")
    columns = [row[1] for row in cursor.fetchall()]
    
    missing_columns = [
        ("linkedin_url", "TEXT"),
        ("linkedin_message", "TEXT"),
        ("linkedin_sent_at", "DATETIME"),
    ]
    
    for col_name, col_type in missing_columns:
        if col_name not in columns:
            print(f"Adding missing column: {col_name}")
            try:
                cursor.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type};")
            except Exception as e:
                print(f"Error adding {col_name}: {e}")
                
    conn.commit()
    print("Database schema fixed!")
    conn.close()

if __name__ == "__main__":
    fix_db()
