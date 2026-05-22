import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, ForeignKey, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

# Attempt to import Base, or create one if not yet defined in the project
try:
    from app.core.database import Base
except ImportError:
    from sqlalchemy.orm import declarative_base
    Base = declarative_base()

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True)
    call_id = Column(UUID(as_uuid=True), ForeignKey("calls.id"), nullable=True)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)
    
    # Meeting Details
    title = Column(String(300), default="Discovery Call - Reach Magnets")
    
    # Prospect Info (snapshot at booking time)
    prospect_name = Column(String(200), nullable=False)
    prospect_phone = Column(String(20), nullable=False)
    prospect_email = Column(String(200), nullable=True)
    prospect_business = Column(String(200), nullable=True)
    
    # Scheduling
    meeting_date = Column(Date, nullable=False)
    meeting_time = Column(String(10), nullable=False)   # e.g. "14:00"
    timezone = Column(String(50), default="America/New_York")
    duration_minutes = Column(Integer, default=15)
    
    # Cal.com
    cal_booking_id = Column(String(200), nullable=True)
    cal_meeting_link = Column(String(500), nullable=True)
    
    # Status
    # Values: confirmed, cancelled, rescheduled, completed, no_show
    status = Column(String(50), default="confirmed")
    
    # What was discussed on call
    discussion_summary = Column(Text, nullable=True)
    prospect_pain_points = Column(Text, nullable=True)
    services_interested = Column(Text, nullable=True)  # e.g. "SEO, Google Ads"
    
    # Follow-up
    sms_sent = Column(Boolean, default=False)
    email_sent = Column(Boolean, default=False)
    reminder_sent = Column(Boolean, default=False)
    
    # RM Team
    assigned_to = Column(String(200), nullable=True)  # (which RM team member handles this)
    rm_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lead = relationship("Lead", back_populates="appointments")
    call = relationship("Call", back_populates="appointment")
    campaign = relationship("Campaign", back_populates="appointments")
