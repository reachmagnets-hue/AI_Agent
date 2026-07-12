import asyncio
import structlog
from datetime import datetime, timezone

from app.services.linkedin_sender import process_hourly_linkedin_tasks
from app.services.campaign_runner import run_active_campaigns

logger = structlog.get_logger(__name__)

class BackgroundScheduler:
    def __init__(self):
        self._task = None
        self._is_running = False
        self.last_sms_run_hour = -1
        self.last_sms_run_day = -1
        
    async def _scheduler_loop(self):
        logger.info("Background scheduler loop started")
        minutes_elapsed = 0
        while self._is_running:
            # 1. Run active campaigns check and dialer trigger
            try:
                await run_active_campaigns()
            except Exception as e:
                logger.error("Error in campaign runner loop", error=str(e))
                
            # 2. Run hourly LinkedIn autopilot tasks
            try:
                if minutes_elapsed % 60 == 0:
                    logger.info("Triggering hourly LinkedIn tasks")
                    await process_hourly_linkedin_tasks()
            except Exception as e:
                logger.error("Error in hourly LinkedIn tasks", error=str(e))
                
            # 3. Run twice-daily SMS follow-ups for interested leads (at 10 AM EST / 14:00 UTC and 4 PM EST / 20:00 UTC)
            try:
                now_utc = datetime.now(timezone.utc)
                if now_utc.hour in [14, 20] and (now_utc.hour != self.last_sms_run_hour or now_utc.day != self.last_sms_run_day):
                    logger.info("Triggering twice-daily SMS follow-ups", hour=now_utc.hour)
                    from app.utils.automations import send_twice_daily_sms_followups
                    await send_twice_daily_sms_followups()
                    self.last_sms_run_hour = now_utc.hour
                    self.last_sms_run_day = now_utc.day
            except Exception as e:
                logger.error("Error in twice-daily SMS follow-ups", error=str(e))
                
            minutes_elapsed += 1
            
            # Sleep for 60 seconds (in 1-second chunks so it remains interruptible on shutdown)
            for _ in range(60):
                if not self._is_running:
                    break
                await asyncio.sleep(1)

    def start(self):
        if not self._is_running:
            self._is_running = True
            self._task = asyncio.create_task(self._scheduler_loop())
            logger.info("Background scheduler started")

    def stop(self):
        if self._is_running:
            self._is_running = False
            if self._task:
                self._task.cancel()
            logger.info("Background scheduler stopped")

scheduler = BackgroundScheduler()
