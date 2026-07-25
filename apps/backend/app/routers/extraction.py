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

async def run_scraper_task(industry: str, location: str, limit: int):
    """Background runner for Google Maps scraping that broadcasts progress updates over WebSockets"""
    print(f"DEBUG: run_scraper_task entered with industry={industry}, location={location}, limit={limit}")
    async def progress_callback(lead_data, current, total):
        await websocket_manager.broadcast({
            "event": "extraction_progress",
            "lead": lead_data,
            "current": current,
            "total": total
        })
        
    try:
        print("DEBUG: Broadcasting extraction_started...")
        await websocket_manager.broadcast({
            "event": "extraction_started",
            "industry": industry,
            "location": location,
            "limit": limit
        })
        
        print("DEBUG: Calling scrape_gmaps...")
        await scrape_gmaps(
            industry=industry,
            location=location,
            limit=limit,
            update_callback=progress_callback
        )
        
        await websocket_manager.broadcast({
            "event": "extraction_completed",
            "industry": industry,
            "location": location
        })
    except Exception as e:
        logger.error("Error in background scraper task", error=str(e))
        await websocket_manager.broadcast({
            "event": "extraction_failed",
            "error": str(e)
        })

@router.post("/scrape")
async def trigger_scrape(request: ScrapeRequest):
    """Triggers the background Google Maps scraper task using asyncio.create_task"""
    print(f"DEBUG: trigger_scrape called with request={request}")
    import asyncio
    asyncio.create_task(
        run_scraper_task(
            industry=request.industry,
            location=request.location,
            limit=request.limit
        )
    )
    print("DEBUG: asyncio.create_task completed scheduling!")
    return {"message": "Data extraction started in background.", "status": "processing"}
