#!/usr/bin/env python3

"""
Reach Magnets AI Voice Calling Agent - Main Application
Production-ready FastAPI application with security, monitoring, and logging.
"""

import time
from typing import Callable
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import structlog

from app.routers import campaigns, calls, webhooks, leads, appointments, retell_webhook, linkedin, emails
from app.core.config import get_settings
from app.utils.logging import get_logger
from app.core.scheduler import scheduler

# Get settings and logger
settings = get_settings()
logger = get_logger(__name__)

# Configure structlog for structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events (startup/shutdown)"""
    logger.info("Starting Reach Magnets AI Voice Calling Agent API")

    # Log configuration
    logger.info(
        f"Environment: {settings.ENVIRONMENT} | Debug: {settings.DEBUG} | Rate Limit: {settings.RATE_LIMIT_PER_MINUTE}"
    )

    # Initialize database tables and verify connection
    try:
        from app.core.database import create_tables, test_connection
        create_tables()
        db_ok = await test_connection()
        logger.info(f"Database connection test: {'OK' if db_ok else 'FAILED'}")
    except Exception as e:
        logger.error("Database connection error", exc_info=True)

    # Start background hourly scheduler
    scheduler.start()
    
    # Register webhook with Retell dynamically if public URL is configured
    if settings.RETELL_API_KEY and settings.RETELL_API_KEY != "your_retell_api_key" and settings.BASE_URL and "localhost" not in settings.BASE_URL:
        try:
            import asyncio
            from app.services.retell_service import register_webhook
            webhook_url = f"{settings.BASE_URL}/api/retell/webhook"
            logger.info(f"Registering Retell webhook dynamically to {webhook_url}")
            asyncio.create_task(register_webhook(webhook_url))
        except Exception as e:
            logger.error(f"Failed to dynamically register Retell webhook: {e}")
    
    yield
    
    logger.info("Shutting down Reach Magnets API")
    # Stop background hourly scheduler
    scheduler.stop()


def create_application() -> FastAPI:
    """Application factory for creating configured FastAPI instances"""

    app = FastAPI(
        title="Reach Magnets AI Voice Calling Agent API",
        description="""
        Production-ready API for automating outbound AI voice calls with
        comprehensive campaign management, real-time analytics, and webhook integration.
        """,
        version="1.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    return app


# Create application instance
app = create_application()





# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Add gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include routers
app.include_router(campaigns.router, prefix="/api/v1", tags=["campaigns"])
app.include_router(calls.router, prefix="/api/v1", tags=["calls"])
app.include_router(webhooks.router, prefix="/api", tags=["webhooks"])
app.include_router(leads.router, prefix="/api/v1", tags=["leads"])
app.include_router(appointments.router, prefix="/api/v1", tags=["appointments"])
app.include_router(linkedin.router, prefix="/api/v1", tags=["linkedin"])
app.include_router(emails.router, prefix="/api/v1", tags=["emails"])
app.include_router(retell_webhook.router)


@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "message": "Reach Magnets AI Voice Calling Agent API",
        "version": "1.2.0",
        "environment": settings.ENVIRONMENT,
        "endpoints": {
            "documentation": "/docs",
            "health": "/health",
        },
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """Comprehensive health check with dependency verification"""
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.2.0",
        "service": "reach-magnets-api",
        "checks": []
    }

    # Check database
    try:
        from app.core.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            health_status["checks"].append({
                "name": "database",
                "status": "healthy"
            })
        finally:
            db.close()
    except Exception as e:
        health_status["checks"].append({
            "name": "database",
            "status": "unhealthy",
            "error": str(e)
        })
        health_status["status"] = "unhealthy"

    # Check Retell service
    if settings.RETELL_API_KEY and settings.RETELL_API_KEY != "your_retell_api_key":
        try:
            from app.services.retell_service import RetellService
            retell = RetellService()
            if retell.is_configured():
                health_status["checks"].append({
                    "name": "retell_service",
                    "status": "healthy"
                })
            else:
                health_status["checks"].append({
                    "name": "retell_service",
                    "status": "unhealthy",
                    "error": "RetellService initialized but not fully configured"
                })
        except Exception as e:
            health_status["checks"].append({
                "name": "retell_service",
                "status": "unhealthy",
                "error": str(e)
            })
    else:
        health_status["checks"].append({
            "name": "retell_service",
            "status": "pending"
        })

    return health_status


# Error handlers
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded", "detail": str(exc)}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled exceptions"""
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "status_code": 500
            }
        }
    )


from app.core.websocket import websocket_manager

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn_config = {
        "host": "0.0.0.0",
        "port": 8000,
        "workers": 4 if settings.is_production() else 1,
        "log_level": settings.LOG_LEVEL.lower(),
        "reload": settings.DEBUG
    }

    uvicorn.run(
        "app.main:app",
        **uvicorn_config
    )