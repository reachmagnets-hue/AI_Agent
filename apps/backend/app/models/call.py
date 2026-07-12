import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

# Attempt to import Base, or create one if not yet defined in the project
try:
    from app.core.database import Base
except ImportError:
    from sqlalchemy.orm import declarative_base
    Base = declarative_base()

class Call(Base):
    __tablename__ = "calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True, index=True)
    
    # Call Identity
    retell_call_id = Column(String(200), nullable=True)  # (Retell's call ID)
    twilio_call_sid = Column(String(200), nullable=True)
    
    # Who Called
    from_number = Column(String(20), nullable=True)  # (our Twilio number)
    to_number = Column(String(20), nullable=True)  # (prospect's number)
    
    # Timing
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, default=0)
    
    # Outcome
    status = Column(String(50), default="initiated", index=True)
    # Values: initiated, ringing, in_progress, completed, no_answer, voicemail, failed, busy
    
    outcome = Column(String(50), nullable=True, index=True)
    # Values: interested, not_interested, meeting_booked, callback_requested, voicemail_left, hung_up, error
    
    # Content
    transcript = Column(Text, nullable=True)  # (full conversation text)
    ai_summary = Column(Text, nullable=True)  # (3-line GPT-4o summary)
    sentiment = Column(String(20), nullable=True)  # (positive, neutral, negative)
    objection_raised = Column(String(250), nullable=True)
    
    # Actions Taken
    meeting_booked = Column(Boolean, default=False, index=True)
    sms_sent = Column(Boolean, default=False)
    email_sent = Column(Boolean, default=False)
    voicemail_dropped = Column(Boolean, default=False)
    
    # Recording
    recording_url = Column(String(500), nullable=True)
    
    # Attempt number
    attempt_number = Column(Integer, default=1)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    lead = relationship("Lead", back_populates="calls")
    campaign = relationship("Campaign", back_populates="calls")
    appointment = relationship("Appointment", uselist=False, back_populates="call")
