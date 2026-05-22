from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ContactStatus(str, Enum):
    PENDING = "pending"
    CALLED = "called"
    FAILED = "failed"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class CallStatus(str, Enum):
    INITIATED = "initiated"
    RINGING = "ringing"
    ANSWERED = "answered"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"


class ContactCreate(BaseModel):
    phone_number: str = Field(..., description="Contact phone number")
    name: Optional[str] = Field(None, description="Contact name")
    company: Optional[str] = Field(None, description="Contact company")

    @validator('phone_number')
    def validate_phone(cls, v):
        if not v:
            raise ValueError('Phone number is required')
        digits = ''.join(filter(str.isdigit, v))
        if len(digits) < 10:
            raise ValueError('Invalid phone number format')
        return v


class ContactResponse(BaseModel):
    id: str
    phone_number: str
    name: Optional[str]
    company: Optional[str]
    status: ContactStatus
    created_at: datetime


class ContactBulkCreate(BaseModel):
    contacts: List[ContactCreate]


class ContactUpdate(BaseModel):
    phone_number: Optional[str]
    name: Optional[str]
    company: Optional[str]
    status: Optional[ContactStatus]


class CampaignCreate(BaseModel):
    name: str = Field(..., description="Campaign name")
    contact_ids: List[str] = Field(..., description="List of contact IDs")


class CampaignResponse(BaseModel):
    id: str
    name: str
    total_contacts: int
    calls_made: int
    calls_answered: int
    status: CampaignStatus
    created_at: datetime


class CallCreate(BaseModel):
    contact_id: str
    campaign_id: str
    vapi_call_id: str


class CallResponse(BaseModel):
    id: str
    contact_id: str
    campaign_id: str
    vapi_call_id: str
    duration_seconds: Optional[int]
    status: CallStatus
    transcript: Optional[str]
    recording_url: Optional[str]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]


class VapiWebhookPayload(BaseModel):
    call_id: str
    status: str
    timestamp: datetime
    data: dict


class PaginatedResponse(BaseModel):
    data: List[dict]
    total: int
    page: int
    limit: int
    pages: int
