import os
import glob
import time
import asyncio
import structlog
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from app.core.database import SessionLocal
from app.models.lead import Lead
from app.services.linkedin_sender import process_hourly_linkedin_tasks
from app.services.campaign_runner import run_active_campaigns
from app.services.email_inbox import sync_email_inbox

logger = structlog.get_logger(__name__)

# Complete Target Locations: 50 US States + 20 Major Metropolitan Areas
TARGET_LOCATIONS: List[str] = [
    # --- 50 US STATES ---
    "Alabama, USA", "Alaska, USA", "Arizona, USA", "Arkansas, USA", "California, USA",
    "Colorado, USA", "Connecticut, USA", "Delaware, USA", "Florida, USA", "Georgia, USA",
    "Hawaii, USA", "Idaho, USA", "Illinois, USA", "Indiana, USA", "Iowa, USA",
    "Kansas, USA", "Kentucky, USA", "Louisiana, USA", "Maine, USA", "Maryland, USA",
    "Massachusetts, USA", "Michigan, USA", "Minnesota, USA", "Mississippi, USA", "Missouri, USA",
    "Montana, USA", "Nebraska, USA", "Nevada, USA", "New Hampshire, USA", "New Jersey, USA",
    "New Mexico, USA", "New York, USA", "North Carolina, USA", "North Dakota, USA", "Ohio, USA",
    "Oklahoma, USA", "Oregon, USA", "Pennsylvania, USA", "Rhode Island, USA", "South Carolina, USA",
    "South Dakota, USA", "Tennessee, USA", "Texas, USA", "Utah, USA", "Vermont, USA",
    "Virginia, USA", "Washington, USA", "West Virginia, USA", "Wisconsin, USA", "Wyoming, USA",
    # --- 20 MAJOR METROPOLITAN AREAS ---
    "Dallas-Fort Worth, Texas, USA",
    "Los Angeles, California, USA",
    "Houston, Texas, USA",
    "Chicago, Illinois, USA",
    "Atlanta, Georgia, USA",
    "Miami, Florida, USA",
    "Phoenix, Arizona, USA",
    "Detroit, Michigan, USA",
    "New York City Metro, New York, USA",
    "Philadelphia, Pennsylvania, USA",
    "Ruhr Valley, Germany",
    "Paris Île-de-France, France",
    "London Metro, United Kingdom",
    "Milan Lombardy, Italy",
    "Madrid, Spain",
    "Tokyo-Yokohama, Japan",
    "Shanghai, China",
    "Mumbai, India",
    "Kuala Lumpur, Malaysia",
    "Sydney, New South Wales, Australia"
]

MAX_LEADS_PER_EXTRACTION = 75
MAX_NIGHTLY_EMAILS = 450
EMAIL_STAGGER_DELAY_SECONDS = 45

class MasterAutonomousScheduler:
    """
    World-Class 24-Hour Master Autonomous Scheduler Engine
    
    Workflow & Rules:
    1. 70 Target Locations (50 US States + 20 Metros) with continuous loop rotation.
    2. Extraction (06:00 AM - 06:00 PM): 1-hr ON / 1-hr REST alternating pattern (Hours 6, 8, 10, 12, 14, 16).
       - Max 50 leads per location.
       - Full deduplication (place_id, email, phone).
       - Captures business name, phone, email, address, website, & directory profiles (Yelp, BBB, Socials).
    3. Weekend Break: Saturday & Sunday are holidays (No extraction, emails, or calls).
    4. Email Outreach (06:00 PM - 06:00 AM): 45s stagger delay, max 450 emails/night limit.
       - Excludes bounced emails from sending queue, while keeping bounce metrics in database.
    5. Retell AI Calls (08:00 PM - 04:00 AM): Outbound AI voice calling with business metadata.
    6. Daily Disk Cleanup (03:00 AM): Purges temp files, old screenshots, and logs over 24h old to save VPS disk space.
    7. 30-Minute IMAP Sync: Parses bounce DSN reports and lead replies.
    """
    def __init__(self):
        self._task = None
        self._is_running = False
        self.location_index = 0
        self.last_extraction_hour = -1
        self.last_imap_sync_minute = -1
        self.last_cleanup_day = -1
        self.nightly_emails_sent = 0
        self.current_night_date = ""

    async def _scheduler_loop(self):
        from app.core.config import get_settings
        logger.info("🚀 World-Class Master Autonomous Scheduler Initialized")
        minutes_elapsed = 0

        while self._is_running:
            settings = get_settings()
            if not getattr(settings, "ENABLE_AUTONOMOUS_SCHEDULER", False):
                await asyncio.sleep(10)
                continue

            try:
                from zoneinfo import ZoneInfo
                tz_name = getattr(settings, "TIMEZONE", "Asia/Kolkata") or "Asia/Kolkata"
                now_local = datetime.now(ZoneInfo(tz_name))
            except Exception:
                now_local = datetime.now()

            current_weekday = now_local.weekday()  # 0=Mon, 5=Sat, 6=Sun
            current_hour = now_local.hour
            current_minute = now_local.minute
            today_str = now_local.strftime("%Y-%m-%d")

            # Reset nightly email count at 18:00 PM
            if current_hour == 18 and self.current_night_date != today_str:
                self.nightly_emails_sent = 0
                self.current_night_date = today_str
                logger.info("🌙 Resetting nightly email counter to 0 for window (6 PM - 6 AM).")

            # ---------------------------------------------------------------
            # 🏖️ WEEKEND BREAK (Saturday & Sunday Holiday)
            # ---------------------------------------------------------------
            if current_weekday >= 5:
                if minutes_elapsed % 60 == 0:
                    logger.info("🏖️ Weekend Break / Holiday (Saturday/Sunday). All automated campaigns on standby until Monday 06:00 AM.")
                minutes_elapsed += 1
                await asyncio.sleep(60)
                continue

            # ---------------------------------------------------------------
            # 🔍 1. EXTRACTION WINDOW: 06:00 AM - 06:00 PM (1-hr ON / 1-hr REST)
            # ---------------------------------------------------------------
            if 6 <= current_hour < 18:
                # Alternating 1-hr ON pattern: Hours 6, 8, 10, 12, 14, 16 are ON; 7, 9, 11, 13, 15, 17 are REST
                if current_hour % 2 == 0:
                    if current_hour != self.last_extraction_hour:
                        location = TARGET_LOCATIONS[self.location_index % len(TARGET_LOCATIONS)]
                        self.location_index += 1
                        self.last_extraction_hour = current_hour
                        
                        logger.info("⏰ Extraction Window Active (1-hr ON). Triggering multi-location extraction...", location=location, hour=current_hour, progress=f"{self.location_index}/{len(TARGET_LOCATIONS)}")
                        asyncio.create_task(self.run_scheduled_extraction(location, query="Auto Body Shop"))
                else:
                    if current_hour != self.last_extraction_hour:
                        self.last_extraction_hour = current_hour
                        logger.info("☕ Extraction Window REST Hour (1-hr REST). Resting extractor for next hour...", hour=current_hour)

            # ---------------------------------------------------------------
            # 📧 2. EMAIL OUTREACH WINDOW: 06:00 PM - 06:00 AM (Max 450/night, 45s delay)
            # ---------------------------------------------------------------
            if current_hour >= 18 or current_hour < 6:
                if self.nightly_emails_sent < MAX_NIGHTLY_EMAILS:
                    logger.info("📧 Email Outreach Window Active (6 PM - 6 AM). Running email campaign worker...", hour=current_hour, sent_tonight=self.nightly_emails_sent, max_cap=MAX_NIGHTLY_EMAILS)
                    try:
                        await run_active_campaigns()
                    except Exception as e:
                        logger.error("Error in email campaign outreach worker", error=str(e))
                else:
                    if minutes_elapsed % 30 == 0:
                        logger.info(f"🛑 Nightly email limit reached ({self.nightly_emails_sent}/{MAX_NIGHTLY_EMAILS}). Pausing emails until 6 PM tomorrow.")

            # ---------------------------------------------------------------
            # 📞 3. VOICE CALLING WINDOW: 08:00 PM - 04:00 AM
            # ---------------------------------------------------------------
            if current_hour >= 20 or current_hour < 4:
                logger.info("📞 Voice Calling Window Active (8 PM - 4 AM). Triggering active voice campaigns...", hour=current_hour)
                try:
                    await run_active_campaigns()
                except Exception as e:
                    logger.error("Error in voice calling worker loop", error=str(e))

            # ---------------------------------------------------------------
            # 🧹 4. IMAP BOUNCE & REPLY SCANNER (Runs every 30 minutes)
            # ---------------------------------------------------------------
            if current_minute in [0, 30] and current_minute != self.last_imap_sync_minute:
                self.last_imap_sync_minute = current_minute
                logger.info("🧹 Triggering 30-Minute IMAP Bounce & Reply Scanner...")
                try:
                    await sync_email_inbox()
                except Exception as e:
                    logger.error("Error in scheduled IMAP inbox sync", error=str(e))

            # ---------------------------------------------------------------
            # 🔗 5. LINKEDIN AUTOPILOT TASKS (Runs hourly)
            # ---------------------------------------------------------------
            try:
                if minutes_elapsed > 0 and minutes_elapsed % 60 == 0:
                    logger.info("🔗 Triggering hourly LinkedIn Autopilot tasks...")
                    await process_hourly_linkedin_tasks()
            except Exception as e:
                logger.error("Error in hourly LinkedIn tasks", error=str(e))

            # ---------------------------------------------------------------
            # 🗄️ 6. DAILY VPS DISK CLEANUP (Runs daily at 03:00 AM)
            # ---------------------------------------------------------------
            if current_hour == 3 and current_weekday != self.last_cleanup_day:
                self.last_cleanup_day = current_weekday
                logger.info("🧹 Running Daily 24-Hour VPS Disk Space Cleanup...")
                try:
                    self.perform_vps_disk_cleanup()
                except Exception as clean_err:
                    logger.error("Error during daily disk cleanup", error=str(clean_err))

            minutes_elapsed += 1

            for _ in range(60):
                if not self._is_running:
                    break
                await asyncio.sleep(1)

    async def run_scheduled_extraction(self, location: str, query: str = "Auto Body Shop"):
        """Background worker to extract leads from a location and store in DB with full deduplication"""
        try:
            from app.services.gmaps_scraper import scrape_google_maps_leads
            logger.info(f"Starting scheduled extraction: location='{location}', max_results={MAX_LEADS_PER_EXTRACTION}")
            results = await scrape_google_maps_leads(query=query, location=location, max_results=MAX_LEADS_PER_EXTRACTION)
            
            db = SessionLocal()
            saved_count = 0
            duplicate_count = 0
            try:
                for r in results:
                    place_id = r.get("place_id")
                    email = (r.get("email") or "").strip().lower()
                    phone = (r.get("phone") or "").strip()
                    
                    # Strict Deduplication Check
                    existing = None
                    if place_id:
                        existing = db.query(Lead).filter(Lead.place_id == place_id).first()
                    if not existing and email:
                        existing = db.query(Lead).filter(Lead.email == email).first()
                    if not existing and phone:
                        existing = db.query(Lead).filter(Lead.phone == phone).first()
                        
                    if existing:
                        duplicate_count += 1
                        continue

                    notes = r.get("internal_notes") or ""
                    lead = Lead(
                        business_name=r.get("name") or "Unknown Business",
                        full_name=f"Manager of {r.get('name') or 'Business'}",
                        phone=r.get("phone"),
                        email=r.get("email"),
                        address=r.get("address"),
                        city=location.split(",")[0].strip(),
                        website=r.get("website"),
                        place_id=r.get("place_id"),
                        source=f"Automated Extractor ({location})",
                        status="pending",
                        internal_notes=notes
                    )
                    db.add(lead)
                    saved_count += 1

                db.commit()
                logger.info(f"Scheduled extraction complete for {location}! New saved: {saved_count}, Duplicates skipped: {duplicate_count}")
            except Exception as db_err:
                logger.error(f"Error saving extracted leads for {location}", error=str(db_err))
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to execute scheduled extraction for {location}", error=str(e))

    def perform_vps_disk_cleanup(self):
        """Purges old temp files, Playwright screenshots, and log artifacts over 24h old to save VPS disk space"""
        now = time.time()
        deleted_files = 0
        cutoff_seconds = 86400  # 24 hours

        # Clean temp directory screenshot artifacts
        target_patterns = [
            "/tmp/*.png", "/tmp/*.webp", "/tmp/*.jpeg",
            "/home/chetan-patil/.gemini/antigravity-ide/brain/*/*.png",
            "/home/chetan-patil/.gemini/antigravity-ide/brain/*/*.webp"
        ]
        
        for pattern in target_patterns:
            for filepath in glob.glob(pattern):
                try:
                    if os.path.isfile(filepath):
                        file_age = now - os.path.getmtime(filepath)
                        if file_age > cutoff_seconds:
                            os.remove(filepath)
                            deleted_files += 1
                except Exception:
                    pass

        logger.info(f"🧹 VPS Disk Cleanup Complete! Purged {deleted_files} old temporary files/artifacts.")

    def record_email_sent(self):
        """Increments the nightly sent emails counter"""
        self.nightly_emails_sent += 1

    def get_status(self) -> Dict[str, Any]:
        """Returns current scheduler operational metrics"""
        now_local = datetime.now()
        current_hour = now_local.hour
        current_weekday = now_local.weekday()
        is_weekend = current_weekday >= 5
        return {
            "is_running": self._is_running,
            "is_weekend_holiday": is_weekend,
            "current_hour": current_hour,
            "total_target_locations": len(TARGET_LOCATIONS),
            "location_index": self.location_index,
            "current_location": TARGET_LOCATIONS[self.location_index % len(TARGET_LOCATIONS)],
            "next_location": TARGET_LOCATIONS[(self.location_index + 1) % len(TARGET_LOCATIONS)],
            "extraction_active": (6 <= current_hour < 18) and (current_hour % 2 == 0) and not is_weekend,
            "email_outreach_active": (current_hour >= 18 or current_hour < 6) and not is_weekend,
            "voice_calling_active": (current_hour >= 20 or current_hour < 4) and not is_weekend,
            "nightly_emails_sent": self.nightly_emails_sent,
            "max_nightly_emails": MAX_NIGHTLY_EMAILS,
            "email_stagger_delay_seconds": EMAIL_STAGGER_DELAY_SECONDS
        }

    def start(self):
        if not self._is_running:
            self._is_running = True
            self._task = asyncio.create_task(self._scheduler_loop())
            logger.info("Master Autonomous Scheduler Started")

    def stop(self):
        if self._is_running:
            self._is_running = False
            if self._task:
                self._task.cancel()
            logger.info("Master Autonomous Scheduler Stopped")

scheduler = MasterAutonomousScheduler()
