import sqlite3
import structlog

logger = structlog.get_logger(__name__)

def add_linkedin_status_column():
    try:
        conn = sqlite3.connect("reachmagnets.db")
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(leads)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "linkedin_status" not in columns:
            cursor.execute("ALTER TABLE leads ADD COLUMN linkedin_status VARCHAR(50) DEFAULT 'pending_approval'")
            cursor.execute("CREATE INDEX ix_leads_linkedin_status ON leads (linkedin_status)")
            conn.commit()
            logger.info("Successfully added linkedin_status column to leads table.")
        else:
            logger.info("Column linkedin_status already exists.")
            
    except Exception as e:
        logger.error(f"Error updating schema: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_linkedin_status_column()
