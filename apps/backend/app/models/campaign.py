import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

# Attempt to import Base, or create one if not yet defined in the project
try:
    from app.core.database import Base
except ImportError:
    from sqlalchemy.orm import declarative_base
    Base = declarative_base()

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)  # e.g. "New York Restaurants May 2026"
    description = Column(Text, nullable=True)
    
    # Settings
    status = Column(String(50), default="draft")
    # Values: draft, active, paused, completed, archived
    
    start_time = Column(String(10), default="09:00")  # (local time to start calling)
    end_time = Column(String(10), default="18:00")
    timezone = Column(String(50), default="America/New_York")
    calls_per_minute = Column(Integer, default=5)
    max_attempts = Column(Integer, default=3)
    
    # AI Script
    ai_script = Column(Text, nullable=True)  # (the pitch script GPT-4o uses)
    ai_persona_name = Column(String(100), default="Alex")
    
    # Stats (computed/cached)
    total_leads = Column(Integer, default=0)
    total_called = Column(Integer, default=0)
    total_answered = Column(Integer, default=0)
    total_booked = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    leads = relationship("Lead", back_populates="campaign")
    calls = relationship("Call", back_populates="campaign")
    appointments = relationship("Appointment", back_populates="campaign")
