from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from app.services.gmaps_scraper import scrape_gmaps
from app.core.websocket import websocket_manager
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/extraction", tags=["Extraction"])

class ScrapeRequest(BaseModel):
    industry: str
    location: str = "USA"
    limit: int = 50

from typing import Dict, Any, List

# Global server-side background extraction state
EXTRACTION_STATE: Dict[str, Any] = {
    "is_running": False,
    "industry": "",
    "location": "USA",
    "limit": 50,
    "current_count": 0,
    "progress_text": "Idle",
    "last_lead": None,
    "error": None
}

async def run_scraper_task(industry: str, location: str, limit: int):
    """Background runner for Google Maps scraping that broadcasts progress updates over WebSockets and maintains server-side state"""
    global EXTRACTION_STATE
    EXTRACTION_STATE["is_running"] = True
    EXTRACTION_STATE["industry"] = industry
    EXTRACTION_STATE["location"] = location
    EXTRACTION_STATE["limit"] = limit
    EXTRACTION_STATE["current_count"] = 0
    EXTRACTION_STATE["progress_text"] = f"Extracting {industry} in {location}..."
    EXTRACTION_STATE["last_lead"] = None
    EXTRACTION_STATE["error"] = None

    async def progress_callback(lead_data, current, total):
        EXTRACTION_STATE["current_count"] = current
        EXTRACTION_STATE["last_lead"] = lead_data
        EXTRACTION_STATE["progress_text"] = f"Extracted {current}/{total} leads: {lead_data.get('name', 'Lead')}"
        await websocket_manager.broadcast({
            "event": "extraction_progress",
            "lead": lead_data,
            "current": current,
            "total": total
        })
        
    try:
        await websocket_manager.broadcast({
            "event": "extraction_started",
            "industry": industry,
            "location": location,
            "limit": limit
        })
        
        await scrape_gmaps(
            industry=industry,
            location=location,
            limit=limit,
            update_callback=progress_callback
        )
        
        EXTRACTION_STATE["is_running"] = False
        EXTRACTION_STATE["progress_text"] = f"Extraction complete for {industry}! All leads saved to DB."
        await websocket_manager.broadcast({
            "event": "extraction_completed",
            "industry": industry,
            "location": location
        })
    except Exception as e:
        logger.error("Error in background scraper task", error=str(e))
        EXTRACTION_STATE["is_running"] = False
        EXTRACTION_STATE["error"] = str(e)
        EXTRACTION_STATE["progress_text"] = f"Scraping failed: {str(e)}"
        await websocket_manager.broadcast({
            "event": "extraction_failed",
            "error": str(e)
        })

@router.get("/status")
async def get_extraction_status():
    """Get active background extraction status from server state"""
    return EXTRACTION_STATE

@router.post("/scrape")
async def trigger_scrape(request: ScrapeRequest):
    """Triggers the background Google Maps scraper task using asyncio.create_task"""
    import asyncio
    asyncio.create_task(
        run_scraper_task(
            industry=request.industry,
            location=request.location,
            limit=request.limit
        )
    )
    return {"message": "Data extraction started in background.", "status": "processing"}
