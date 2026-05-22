from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func
from typing import List, Optional
from datetime import datetime, date, timedelta
from uuid import UUID

from app.core.database import get_db
from app.models.appointment import Appointment
from app.models.call import Call
from app.models.lead import Lead

router = APIRouter(prefix="/appointments", tags=["appointments"])

@router.get("/")
def get_appointments(
    meeting_date: Optional[date] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    status: Optional[str] = Query(None),
    campaign_id: Optional[UUID] = Query(None),
    search: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    sort_by: str = Query("meeting_date"),
    sort_order: str = Query("asc"),
    db: Session = Depends(get_db)
):
    """GET appointments with comprehensive query filter support"""
    query = db.query(Appointment).join(Lead, Appointment.lead_id == Lead.id)

    if meeting_date:
        query = query.filter(Appointment.meeting_date == meeting_date)
    if date_from:
        query = query.filter(Appointment.meeting_date >= date_from)
    if date_to:
        query = query.filter(Appointment.meeting_date <= date_to)
    if status:
        query = query.filter(Appointment.status == status)
    if campaign_id:
        query = query.filter(Appointment.campaign_id == campaign_id)
    if assigned_to:
        query = query.filter(Appointment.assigned_to == assigned_to)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Appointment.prospect_name.ilike(search_filter),
                Appointment.prospect_business.ilike(search_filter),
                Appointment.prospect_email.ilike(search_filter)
            )
        )

    # Sort
    sort_column = getattr(Appointment, sort_by, Appointment.meeting_date)
    if sort_order.lower() == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)

    total = query.count()
    pages = (total + limit - 1) // limit
    appointments = query.offset((page - 1) * limit).limit(limit).all()

    return {
        "appointments": appointments,
        "total": total,
        "page": page,
        "pages": pages
    }

@router.get("/today")
def get_today_appointments(db: Session = Depends(get_db)):
    """Fetch meetings scheduled for today, ordered by time"""
    today_val = date.today()
    meetings = db.query(Appointment)\
        .filter(Appointment.meeting_date == today_val)\
        .order_by(Appointment.meeting_time).all()
    return meetings

@router.get("/upcoming")
def get_upcoming_appointments(db: Session = Depends(get_db)):
    """Fetch meetings scheduled for the next 7 days"""
    today_val = date.today()
    end_val = today_val + timedelta(days=7)
    meetings = db.query(Appointment)\
        .filter(Appointment.meeting_date >= today_val, Appointment.meeting_date <= end_val)\
        .order_by(Appointment.meeting_date, Appointment.meeting_time).all()
    return meetings

@router.get("/stats")
def get_appointment_stats(db: Session = Depends(get_db)):
    """Retrieve statistical review metrics of bookings"""
    today_val = date.today()
    this_week_val = today_val + timedelta(days=7)
    this_month_val = today_val + timedelta(days=30)
    
    today_count = db.query(Appointment).filter(Appointment.meeting_date == today_val).count()
    week_count = db.query(Appointment).filter(Appointment.meeting_date >= today_val, Appointment.meeting_date <= this_week_val).count()
    month_count = db.query(Appointment).filter(Appointment.meeting_date >= today_val, Appointment.meeting_date <= this_month_val).count()

    status_counts = db.query(Appointment.status, func.count(Appointment.id)).group_by(Appointment.status).all()
    by_status = {status: count for status, count in status_counts}

    total_resolved = db.query(Appointment).filter(Appointment.status.in_(["completed", "no_show"])).count()
    no_shows = db.query(Appointment).filter(Appointment.status == "no_show").count()
    
    no_show_rate = (no_shows / total_resolved * 100) if total_resolved > 0 else 0.0
    completion_rate = (db.query(Appointment).filter(Appointment.status == "completed").count() / total_resolved * 100) if total_resolved > 0 else 0.0

    return {
        "today": today_count,
        "this_week": week_count,
        "this_month": month_count,
        "by_status": by_status,
        "no_show_rate": round(no_show_rate, 1),
        "completion_rate": round(completion_rate, 1)
    }

@router.get("/{appointment_id}")
def get_appointment_detail(appointment_id: UUID, db: Session = Depends(get_db)):
    """Retrieve single appointment with full lead & linked call transcript info"""
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    call_transcript = None
    if appt.call_id:
        call_record = db.query(Call).filter(Call.id == appt.call_id).first()
        if call_record:
            call_transcript = call_record.transcript

    return {
        "appointment": appt,
        "lead": appt.lead,
        "call_transcript": call_transcript
    }

@router.patch("/{appointment_id}")
def update_appointment(
    appointment_id: UUID,
    status: Optional[str] = None,
    rm_notes: Optional[str] = None,
    assigned_to: Optional[str] = None,
    reminder_sent: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Update booking details, status, or notes"""
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if status is not None:
        appt.status = status
    if rm_notes is not None:
        appt.rm_notes = rm_notes
    if assigned_to is not None:
        appt.assigned_to = assigned_to
    if reminder_sent is not None:
        appt.reminder_sent = reminder_sent

    db.commit()
    db.refresh(appt)
    return appt
