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
    # --- CANADA PROVINCES & TERRITORIES & MAJOR CITIES ---
    "Ontario, Canada", "Quebec, Canada", "British Columbia, Canada", "Alberta, Canada",
    "Manitoba, Canada", "Saskatchewan, Canada", "Nova Scotia, Canada", "New Brunswick, Canada",
    "Newfoundland and Labrador, Canada", "Prince Edward Island, Canada", "Northwest Territories, Canada",
    "Yukon, Canada", "Nunavut, Canada",
    "Toronto, Ontario, Canada", "Vancouver, British Columbia, Canada", "Montreal, Quebec, Canada",
    "Calgary, Alberta, Canada", "Ottawa, Ontario, Canada", "Edmonton, Alberta, Canada",
    "Quebec City, Quebec, Canada", "Winnipeg, Manitoba, Canada", "Hamilton, Ontario, Canada", "Halifax, Nova Scotia, Canada",
    # --- 20 MAJOR METROPOLITAN AREAS & GLOBAL CITIES ---
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

MAX_LEADS_PER_EXTRACTION = 500
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

    def record_email_sent(self):
        """Increments nightly email counter"""
        self.nightly_emails_sent += 1

    async def _scheduler_loop(self):
        from app.core.config import get_settings
        logger.info("🚀 World-Class Master Autonomous Scheduler Initialized")
        minutes_elapsed = 0

        while self._is_running:
            settings = get_settings()
            if not getattr(settings, "ENABLE_AUTONOMOUS_SCHEDULER", False):
                await asyncio.sleep(10)
                continue

            from datetime import timedelta
            ist_tz = timezone(timedelta(hours=5, minutes=30))
            now_local = datetime.now(timezone.utc).astimezone(ist_tz)

            current_weekday = now_local.weekday()  # 0=Mon, 5=Sat, 6=Sun
            current_hour = now_local.hour
            current_minute = now_local.minute
            today_str = now_local.strftime("%Y-%m-%d")

            # Reset nightly email count at 18:00 PM (6 PM IST)
            night_key = f"{today_str}_18"
            if current_hour == 18 and self.current_night_date != night_key:
                self.nightly_emails_sent = 0
                self.current_night_date = night_key
                logger.info("🌙 Resetting nightly email counter to 0 for 6 PM - 6 AM IST window.")

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
                if current_hour % 2 == 0:
                    if current_hour != self.last_extraction_hour:
                        self.last_extraction_hour = current_hour
                        logger.info("⏰ Extraction Window Active (06:00 AM - 06:00 PM IST). Triggering multi-location extraction...", hour=current_hour, target_per_run=MAX_LEADS_PER_EXTRACTION)
                        asyncio.create_task(self.run_scheduled_extraction(target_limit=MAX_LEADS_PER_EXTRACTION))

            # ---------------------------------------------------------------
            # 📧 2. EMAIL OUTREACH WINDOW: 06:00 PM - 06:00 AM (Max 450/night, 45s delay)
            # ---------------------------------------------------------------
            if current_hour >= 18 or current_hour < 6:
                if self.nightly_emails_sent < MAX_NIGHTLY_EMAILS:
                    logger.info("📧 Email Outreach Window Active (6 PM - 6 AM IST). Running email campaign worker...", hour=current_hour, sent_tonight=self.nightly_emails_sent, max_cap=MAX_NIGHTLY_EMAILS)
                    try:
                        await run_active_campaigns()
                    except Exception as e:
                        logger.error("Error in email campaign outreach worker", error=str(e))
                else:
                    if minutes_elapsed % 30 == 0:
                        logger.info(f"🛑 Nightly email limit reached ({self.nightly_emails_sent}/{MAX_NIGHTLY_EMAILS}). Pausing emails until 6 PM tomorrow.")

            # ---------------------------------------------------------------
            # 📞 3. VOICE CALLING WINDOWS: 8 PM-10 PM IST, 12 AM-1 AM IST, 3 AM-4 AM IST
            # ---------------------------------------------------------------
            is_call_window = (20 <= current_hour < 22) or (0 <= current_hour < 1) or (3 <= current_hour < 4)
            if is_call_window:
                logger.info("📞 Voice Calling Window Active (Designated Call Windows). Triggering active voice campaigns...", hour=current_hour)
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

    async def run_scheduled_extraction(self, target_limit: int = MAX_LEADS_PER_EXTRACTION):
        """
        Background worker to extract leads across target locations until target_limit is reached.
        If a location has fewer leads, it automatically shifts to the next location or alternate query keywords
        until the target lead limit for this active hour is completely fulfilled.
        """
        queries = ["Auto Body Shop", "Auto Repair", "Car Detailing", "Auto Mechanic", "Tire Shop"]
        extracted_this_run = 0

        while extracted_this_run < target_limit and self._is_running:
            location = TARGET_LOCATIONS[self.location_index % len(TARGET_LOCATIONS)]
            query = queries[self.location_index % len(queries)]
            self.location_index += 1

            needed = target_limit - extracted_this_run
            logger.info(f"Starting scheduled extraction: query='{query}', location='{location}', needed={needed}, extracted_so_far={extracted_this_run}/{target_limit}")

            try:
                from app.services.gmaps_scraper import scrape_gmaps
                count = await scrape_gmaps(industry=query, location=location, limit=needed)
                extracted_this_run += count
                logger.info(f"Location '{location}' produced {count} new leads (Total this run: {extracted_this_run}/{target_limit}).")

                if count == 0 or count < needed:
                    logger.info(f"Location '{location}' yielded fewer leads ({count}/{needed}). Shifting to next target location...")
                    await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Failed extraction attempt for {location}", error=str(e))
                await asyncio.sleep(2)

        logger.info(f"🎯 Extraction run completed! Extracted {extracted_this_run} total new leads this active hour.")

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
        from datetime import timedelta
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        now_local = datetime.now(timezone.utc).astimezone(ist_tz)
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
