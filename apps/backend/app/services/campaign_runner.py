import uuid
import asyncio
import structlog
from datetime import datetime, timezone, timedelta
from uuid import UUID
from typing import Any, cast
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, uuid_match
from app.models.campaign import Campaign
from app.models.lead import Lead

logger = structlog.get_logger(__name__)

# Keep track of campaigns currently running their dialer loops in memory to avoid duplicate tasks
RUNNING_CAMPAIGNS = set()

def is_within_allowed_run_windows() -> bool:
    """
    Checks if current local time (IST, UTC+5:30) falls within the allowed CALL windows:
    - 8:00 PM - 10:00 PM (20:00 to 22:00)
    - 12:00 AM - 1:00 AM (00:00 to 01:00)
    - 3:00 AM - 4:00 AM (03:00 to 04:00)
    NOTE: Email campaigns use a separate check and bypass this.
    """
    from app.core.config import get_settings
    settings = get_settings()
    if settings.BYPASS_TIME_GATING:
        return True

    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(timezone.utc).astimezone(ist_tz)
    
    hour = now_ist.hour
    
    # Check Window 1: 8:00 PM - 10:00 PM (20:00 - 22:00)
    if 20 <= hour < 22:
        return True
        
    # Check Window 2: 12:00 AM - 1:00 AM (00:00 - 01:00)
    if hour == 0:
        return True
        
    # Check Window 3: 3:00 AM - 4:00 AM (03:00 - 04:00)
    if hour == 3:
        return True
        
    return False


def is_within_email_send_window() -> bool:
    """
    Email outreach runs 24/7 (Monday through Saturday).
    Sunday is a holiday (Sunday Off).
    """
    return True

async def run_active_campaigns():
    """
    Scans for active campaigns and spawns email and calling loops:
    - Email outreach runs continuously across database leads with 45s stagger delay
    - Call campaigns run during specific allowed call windows
    """
    db = SessionLocal()
    try:
        from app.core.scheduler import scheduler, MAX_DAILY_EMAILS
        from datetime import timezone
        
        # Check if email outreach is below daily cap and start master dispatcher immediately
        if scheduler.daily_emails_sent < MAX_DAILY_EMAILS:
            if "master_email_runner" not in RUNNING_CAMPAIGNS:
                asyncio.create_task(run_master_email_dispatch_loop())

        active_campaigns = db.query(Campaign).filter(Campaign.status == "active").all()
        for campaign in active_campaigns:
            if campaign.id in RUNNING_CAMPAIGNS:
                continue

            camp_type = getattr(campaign, "campaign_type", None) or ""
            camp_name = getattr(campaign, "name", "") or ""

            if camp_type == "email" or "email" in camp_name.lower():
                asyncio.create_task(run_campaign_dialer_loop(cast(Any, campaign.id)))
            else:
                if is_within_allowed_run_windows():
                    asyncio.create_task(run_campaign_dialer_loop(cast(Any, campaign.id)))
    except Exception as e:
        logger.error("Error checking active campaigns in background runner", error=str(e))
    finally:
        db.close()


async def run_master_email_dispatch_loop():
    """
    Autonomous Master Email Dispatcher: Continuously picks the highest-priority lead from reachmagnets.db
    (Step 3 -> Step 2 -> Step 1) and dispatches AI-personalized emails via SMTP with 45s stagger delay.
    """
    if "master_email_runner" in RUNNING_CAMPAIGNS:
        return
    RUNNING_CAMPAIGNS.add("master_email_runner")
    logger.info("🚀 Starting Master Autonomous Email Dispatch Loop...")

    try:
        while True:
            from app.core.scheduler import scheduler, MAX_DAILY_EMAILS, EMAIL_STAGGER_DELAY_SECONDS
            from datetime import datetime, timezone, timedelta
            from sqlalchemy import or_ as sa_or_

            # Check daily limit and Sunday holiday
            ist_tz = timezone(timedelta(hours=5, minutes=30))
            now_ist = datetime.now(timezone.utc).astimezone(ist_tz)
            if now_ist.weekday() == 6:  # Sunday Off
                logger.info("🏖️ Sunday Email Outreach Holiday. Master Email Dispatch Loop pausing until Monday.")
                break

            if scheduler.daily_emails_sent >= MAX_DAILY_EMAILS:
                logger.info(f"🛑 Daily email limit reached ({scheduler.daily_emails_sent}/{MAX_DAILY_EMAILS}). Resuming tomorrow.")
                break

            db = SessionLocal()
            lead_id = None
            current_step = 1
            to_email = None
            to_name = "Shop Owner"
            biz_name = ""
            biz_type = "Auto Body Shop"
            try:
                two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)

                # 1. Step 3 (Follow-Up #2): Sent 48h after Step 2
                lead = db.query(Lead).filter(
                    Lead.email_sent_at <= two_days_ago,
                    Lead.email.isnot(None),
                    Lead.email != "",
                    Lead.internal_notes.like("%[Email Step 2]%"),
                    ~Lead.internal_notes.like("%[Email Step 3]%"),
                    sa_or_(Lead.is_dnc == False, Lead.is_dnc.is_(None)),
                    sa_or_(Lead.is_active == True, Lead.is_active.is_(None)),
                    sa_or_(Lead.opted_out == False, Lead.opted_out.is_(None)),
                    sa_or_(Lead.email_status.is_(None), Lead.email_status.notin_(["bounced", "blocked", "replied", "clicked"])),
                    Lead.email_bounced_at.is_(None)
                ).order_by(Lead.email_sent_at).first()
                if lead:
                    current_step = 3

                # 2. Step 2 (Follow-Up #1): Sent 48h after Step 1
                if not lead:
                    lead = db.query(Lead).filter(
                        Lead.email_sent_at <= two_days_ago,
                        Lead.email.isnot(None),
                        Lead.email != "",
                        sa_or_(Lead.internal_notes.like("%[Email Step 1]%"), Lead.email_sent_at.isnot(None)),
                        ~Lead.internal_notes.like("%[Email Step 2]%"),
                        ~Lead.internal_notes.like("%[Email Step 3]%"),
                        sa_or_(Lead.is_dnc == False, Lead.is_dnc.is_(None)),
                        sa_or_(Lead.is_active == True, Lead.is_active.is_(None)),
                        sa_or_(Lead.opted_out == False, Lead.opted_out.is_(None)),
                        sa_or_(Lead.email_status.is_(None), Lead.email_status.notin_(["bounced", "blocked", "replied", "clicked"])),
                        Lead.email_bounced_at.is_(None)
                    ).order_by(Lead.email_sent_at).first()
                    if lead:
                        current_step = 2

                # 3. Step 1 (Initial Email - Fresh Leads)
                if not lead:
                    lead = db.query(Lead).filter(
                        Lead.email_sent_at.is_(None),
                        Lead.email.isnot(None),
                        Lead.email != "",
                        sa_or_(Lead.is_dnc == False, Lead.is_dnc.is_(None)),
                        sa_or_(Lead.is_active == True, Lead.is_active.is_(None)),
                        sa_or_(Lead.opted_out == False, Lead.opted_out.is_(None)),
                        sa_or_(Lead.email_status.is_(None), Lead.email_status.notin_(["bounced", "blocked", "replied", "clicked"])),
                        Lead.email_bounced_at.is_(None)
                    ).order_by(Lead.created_at).first()
                    if lead:
                        current_step = 1

                if not lead:
                    logger.info("No more email leads pending in database. Sleeping 60s...")
                    break

                lead_id = str(lead.id)
                to_email = str(lead.email)
                to_name = str(lead.full_name or lead.contact_name or "Shop Owner")
                biz_name = str(lead.business_name or "")
                biz_type = str(lead.business_type or "Auto Body Shop")
            finally:
                db.close()

            if lead_id and to_email:
                logger.info(f"📧 Master Dispatcher: Sending Step {current_step} Email to {to_email} ({biz_name})...")
                from app.utils.automations import send_outreach_email
                success = await send_outreach_email(
                    to_email=to_email,
                    to_name=to_name,
                    business_name=biz_name,
                    business_type=biz_type,
                    lead_id=lead_id,
                    step=current_step
                )

                db_update = SessionLocal()
                try:
                    lead_obj = db_update.query(Lead).filter(uuid_match(Lead.id, lead_id)).first()
                    if lead_obj:
                        now_utc = datetime.now(timezone.utc)
                        lead_obj.email_sent_at = now_utc  # type: ignore
                        if success:
                            lead_obj.email_status = "sent"  # type: ignore
                            current_notes = getattr(lead_obj, "internal_notes", "") or ""
                            step_tag = f"[Email Step {current_step}]"
                            if step_tag not in current_notes:
                                lead_obj.internal_notes = f"{current_notes} {step_tag}".strip()  # type: ignore
                            scheduler.record_email_sent()
                            logger.info(f"✅ Step {current_step} Email successfully sent to {to_email}. Daily total: {scheduler.daily_emails_sent}/{MAX_DAILY_EMAILS}")
                        else:
                            lead_obj.email_status = "failed"  # type: ignore
                        db_update.commit()
                except Exception as update_err:
                    logger.error("Error updating lead status in master dispatcher", error=str(update_err))
                finally:
                    db_update.close()

            await asyncio.sleep(EMAIL_STAGGER_DELAY_SECONDS)
    except Exception as e:
        logger.error("Error in master email dispatch loop", error=str(e))
    finally:
        RUNNING_CAMPAIGNS.remove("master_email_runner")

async def run_campaign_dialer_loop(campaign_id: UUID):
    """
    Sequentially processes pending leads for an active campaign, making outbound emails or calls.
    Respects rate limits, sending/calling hours, and automatically handles pause/completion states.
    """
    if campaign_id in RUNNING_CAMPAIGNS:
        return
        
    RUNNING_CAMPAIGNS.add(campaign_id)
    logger.info("Campaign loop started", campaign_id=str(campaign_id))
    
    try:
        from app.services.retell_service import RetellService
        from app.routers.campaigns import make_single_call_sqlalchemy
        
        retell_service = RetellService()
        
        while True:
            db = SessionLocal()
            lead_id = None
            is_email = False
            is_linkedin = False
            try:
                campaign = db.query(Campaign).filter(uuid_match(Campaign.id, campaign_id)).first()
                if not campaign or campaign.status != "active":
                    logger.info("Exiting campaign loop: campaign is no longer active", campaign_id=str(campaign_id))
                    break
                
                camp_type = getattr(campaign, "campaign_type", None) or ""
                camp_name = getattr(campaign, "name", "") or ""
                is_email = camp_type == "email" or ("email" in camp_name.lower() or "e mail" in camp_name.lower())
                is_linkedin = camp_type == "linkedin" or ("linkedin" in camp_name.lower() or "linked in" in camp_name.lower())

                # Check limit for email campaign
                if is_email:
                    from app.core.scheduler import scheduler, MAX_DAILY_EMAILS
                    if scheduler.daily_emails_sent >= MAX_DAILY_EMAILS:
                        logger.info("Exiting email campaign loop: Daily limit reached (500 max)", campaign_id=str(campaign_id), sent_today=scheduler.daily_emails_sent)
                        break
                elif not is_linkedin:
                    # Check Master Calling Switch for Voice Call campaigns
                    from app.core.config import get_settings
                    settings = get_settings()
                    if not getattr(settings, "CALLING_ENABLED", True):
                        logger.info("Exiting call campaign loop: Master AI Voice Calling switch is OFF", campaign_id=str(campaign_id))
                        break
                    if not is_within_allowed_run_windows():
                        logger.info("Exiting campaign loop: outside allowed calling windows", campaign_id=str(campaign_id))
                        break
                
                # Intercept LinkedIn campaign
                if is_linkedin:
                    logger.info("Intercepted LinkedIn campaign. Starting LinkedIn outreach flow.", campaign_name=campaign.name)
                    from app.services.linkedin_sender import send_linkedin_campaign
                    res = await send_linkedin_campaign(str(campaign_id))
                    logger.info("LinkedIn campaign execution done", result=res)
                    setattr(campaign, "status", "completed")
                    setattr(campaign, "completed_at", datetime.now(timezone.utc))
                    db.commit()
                    break
                    
                # Pull next pending lead (excluding bounced/replied/clicked leads)
                from sqlalchemy import or_ as sa_or_
                current_step = 1
                if is_email:
                    two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
                    
                    # 1. Step 3 (Follow-Up #2): Sent 48h after Step 2
                    lead = db.query(Lead).filter(
                        Lead.email_sent_at <= two_days_ago,
                        Lead.email.isnot(None),
                        Lead.email != "",
                        Lead.internal_notes.like("%[Email Step 2]%"),
                        ~Lead.internal_notes.like("%[Email Step 3]%"),
                        sa_or_(Lead.is_dnc == False, Lead.is_dnc.is_(None)),
                        sa_or_(Lead.is_active == True, Lead.is_active.is_(None)),
                        sa_or_(Lead.opted_out == False, Lead.opted_out.is_(None)),
                        Lead.email_status.notin_(["bounced", "blocked", "replied", "clicked"]),
                        Lead.email_bounced_at.is_(None)
                    ).order_by(Lead.email_sent_at).first()
                    if lead:
                        current_step = 3

                    # 2. Step 2 (Follow-Up #1): Sent 48h after Step 1
                    if not lead:
                        lead = db.query(Lead).filter(
                            Lead.email_sent_at <= two_days_ago,
                            Lead.email.isnot(None),
                            Lead.email != "",
                            sa_or_(Lead.internal_notes.like("%[Email Step 1]%"), Lead.email_sent_at.isnot(None)),
                            ~Lead.internal_notes.like("%[Email Step 2]%"),
                            ~Lead.internal_notes.like("%[Email Step 3]%"),
                            sa_or_(Lead.is_dnc == False, Lead.is_dnc.is_(None)),
                            sa_or_(Lead.is_active == True, Lead.is_active.is_(None)),
                            sa_or_(Lead.opted_out == False, Lead.opted_out.is_(None)),
                            Lead.email_status.notin_(["bounced", "blocked", "replied", "clicked"]),
                            Lead.email_bounced_at.is_(None)
                        ).order_by(Lead.email_sent_at).first()
                        if lead:
                            current_step = 2

                    # 3. Step 1 (Initial Email - Fresh Leads)
                    if not lead:
                        lead = db.query(Lead).filter(
                            Lead.email_sent_at.is_(None),
                            Lead.email.isnot(None),
                            Lead.email != "",
                            sa_or_(Lead.is_dnc == False, Lead.is_dnc.is_(None)),
                            sa_or_(Lead.is_active == True, Lead.is_active.is_(None)),
                            sa_or_(Lead.opted_out == False, Lead.opted_out.is_(None)),
                            sa_or_(
                                Lead.email_status.is_(None),
                                Lead.email_status.notin_(["bounced", "blocked", "replied", "clicked"])
                            ),
                            Lead.email_bounced_at.is_(None)
                        ).order_by(Lead.created_at).first()
                        if lead:
                            current_step = 1
                else:
                    lead = db.query(Lead).filter(
                        uuid_match(Lead.campaign_id, campaign_id),
                        Lead.status == "pending",
                        Lead.is_dnc == False,
                        Lead.is_active == True
                    ).order_by(Lead.created_at).first()
                
                if not lead:
                    logger.info("No more pending leads found for campaign", campaign_id=str(campaign_id))
                    if not is_email:
                        try:
                            db.query(Campaign).filter(uuid_match(Campaign.id, campaign_id)).update({
                                "status": "completed",
                                "completed_at": datetime.now(timezone.utc)
                            }, synchronize_session=False)
                            db.commit()
                        except Exception as err:
                            logger.warning("Could not set campaign status to completed", campaign_id=str(campaign_id), error=str(err))
                    break
                    
                lead_id = cast(Any, lead.id)
            except Exception as e:
                logger.error("Error inside campaign loop db query", campaign_id=str(campaign_id), error=str(e))
                break
            finally:
                db.close()

            if is_email:
                logger.info("Processing email campaign lead", campaign_id=str(campaign_id), lead_id=str(lead_id), step=current_step)
                db_update = SessionLocal()
                try:
                    db_item = db_update.query(Lead).filter(uuid_match(Lead.id, lead_id)).first()
                    if db_item:
                        if db_item.email:
                            from app.utils.automations import send_outreach_email
                            db_item.status = "calling"  # type: ignore
                            db_update.commit()
                            
                            success = await send_outreach_email(
                                to_email=str(db_item.email),
                                to_name=str(db_item.full_name) if db_item.full_name else "there",
                                business_name=str(db_item.business_name) if db_item.business_name else None,
                                business_type=str(db_item.business_type) if db_item.business_type else None,
                                lead_id=str(db_item.id),
                                step=current_step
                            )
                            
                            db_update.expire_all()
                            db_item = db_update.query(Lead).filter(uuid_match(Lead.id, lead_id)).first()
                            if db_item:
                                db_item.status = "called" if success else "failed"  # type: ignore
                                if success:
                                    now_utc = datetime.now(timezone.utc)
                                    db_item.email_sent_at = now_utc  # type: ignore
                                    if not db_item.email_delivered_at:
                                        db_item.email_delivered_at = now_utc  # type: ignore
                                    if db_item.email_status not in ["opened", "clicked", "replied", "bounced", "blocked"]:
                                        db_item.email_status = "delivered"  # type: ignore
                                    
                                    notes = str(db_item.internal_notes or "")
                                    step_tag = f"[Email Step {current_step}]"
                                    if step_tag not in notes:
                                        db_item.internal_notes = f"{notes} {step_tag}".strip()
                                db_update.commit()
                            
                            try:
                                from app.core.scheduler import scheduler
                                scheduler.record_email_sent()
                            except Exception:
                                pass
                            logger.info("Email outreach complete for lead", lead_id=str(lead_id), success=success)
                        else:
                            db_item.status = "failed"  # type: ignore
                            db_item.internal_notes = "Skipped: Lead has no email address."  # type: ignore
                            db_update.commit()
                            logger.warning("Lead skipped: no email", lead_id=str(lead_id))
                except Exception as update_err:
                    logger.error("Error processing email campaign lead", lead_id=str(lead_id), error=str(update_err))
                finally:
                    db_update.close()
                
                # 45-second delay between emails (Gmail rate limit protection)
                logger.info("Enforcing 45-second stagger delay between email sends...")
                await asyncio.sleep(45)
            else:
                # Place outbound call
                logger.info("Placing outbound call for lead", campaign_id=str(campaign_id), lead_id=str(lead_id))
                await make_single_call_sqlalchemy(lead_id, campaign_id, retell_service)
                
                # Rate limit cooldown (1.5 seconds)
                await asyncio.sleep(1.5)
            
    except Exception as e:
        logger.error("Error in campaign dialer loop executor", campaign_id=str(campaign_id), error=str(e))
    finally:
        RUNNING_CAMPAIGNS.discard(campaign_id)
        logger.info("Dialer loop stopped for campaign", campaign_id=str(campaign_id))

def start_campaign_dialer(campaign_id: UUID):
    """Convenience trigger to immediately spin up the campaign dialer loop"""
    asyncio.create_task(run_campaign_dialer_loop(campaign_id))
