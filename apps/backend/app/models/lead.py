import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

# Attempt to import Base, or create one if not yet defined in the project
try:
    from app.core.database import Base
except ImportError:
    from sqlalchemy.orm import declarative_base
    Base = declarative_base()

class Lead(Base):
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Identity
    full_name = Column(String(200), nullable=True)
    business_name = Column(String(200), nullable=True, index=True)
    phone = Column(String(20), nullable=False, index=True)
    email = Column(String(200), nullable=True, index=True)
    website = Column(String(300), nullable=True)
    
    # Business Info
    # e.g. restaurant, clinic, salon, real_estate, retail, other
    business_type = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(10), default="US")
    
    # Campaign Info
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True, index=True)
    source = Column(String(100), default="csv_upload")
    imported_at = Column(DateTime, default=datetime.utcnow)
    
    # CRM Status
    # Values: pending, calling, no_answer, voicemail, not_interested, interested, meeting_booked, follow_up, closed_won, closed_lost
    status = Column(String(50), default="pending", index=True)
    
    # (0-100)
    lead_score = Column(Integer, default=0)
    
    # (low, normal, high, urgent)
    priority = Column(String(20), default="normal")
    
    # Call Tracking
    total_calls = Column(Integer, default=0)
    last_called_at = Column(DateTime, nullable=True)
    next_call_at = Column(DateTime, nullable=True)
    call_attempts = Column(Integer, default=0)
    
    # Notes
    # Reach Magnets team notes
    internal_notes = Column(Text, nullable=True)
    # AI generated lead summary
    ai_summary = Column(Text, nullable=True)
    
    # LinkedIn Outreach fields
    linkedin_url = Column(String(300), nullable=True, index=True)
    linkedin_message = Column(Text, nullable=True)
    linkedin_sent_at = Column(DateTime, nullable=True)
    linkedin_status = Column(String(50), default="pending_approval", index=True)
    
    # Email Outreach fields
    email_message = Column(Text, nullable=True)
    email_sent_at = Column(DateTime, nullable=True)
    
    # Flags
    # Do Not Call
    is_dnc = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, index=True)
    opted_out = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    calls = relationship("Call", back_populates="lead")
    appointments = relationship("Appointment", back_populates="lead")
    campaign = relationship("Campaign", back_populates="leads")
