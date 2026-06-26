import asyncio
import structlog
from datetime import datetime, timezone

from app.services.linkedin_sender import process_hourly_linkedin_tasks

logger = structlog.get_logger(__name__)

class BackgroundScheduler:
    def __init__(self):
        self._task = None
        self._is_running = False
        
    async def _hourly_loop(self):
        logger.info("Hourly background scheduler loop started")
        while self._is_running:
            try:
                logger.info("Triggering hourly LinkedIn tasks")
                await process_hourly_linkedin_tasks()
            except Exception as e:
                logger.error("Error in hourly LinkedIn tasks", error=str(e))
                
            # Sleep for 1 hour (3600 seconds)
            # Sleep in small chunks so we can interrupt it cleanly if needed
            for _ in range(60):
                if not self._is_running:
                    break
                await asyncio.sleep(60)

    def start(self):
        if not self._is_running:
            self._is_running = True
            self._task = asyncio.create_task(self._hourly_loop())
            logger.info("Background scheduler started")

    def stop(self):
        if self._is_running:
            self._is_running = False
            if self._task:
                self._task.cancel()
            logger.info("Background scheduler stopped")

scheduler = BackgroundScheduler()
