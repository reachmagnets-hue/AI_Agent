import asyncio
import uuid
import structlog
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.lead import Lead

logger = structlog.get_logger(__name__)

# Try to import Playwright
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("playwright not installed. LinkedIn scraper will run in simulated mode.")

async def scrape_linkedin_leads(industry: str, limit: int = 50, campaign_id: Optional[str] = None, location: Optional[str] = None) -> Dict[str, Any]:
    """
    Search and scrape LinkedIn profiles for the given industry.
    Finds CEOs/Founders/Owners in the target industry.
    """
    settings = get_settings()
    cookie = settings.LINKEDIN_SESSION_COOKIE
    
    logger.info("Starting LinkedIn lead search scraper", industry=industry, limit=limit, campaign_id=campaign_id, location=location)
    
    # Check if we should run simulated/mock scraping
    if not PLAYWRIGHT_AVAILABLE or not cookie or cookie == "your_linkedin_session_cookie":
        logger.info("Running LinkedIn scraping in SIMULATED mode (Playwright unavailable or li_at cookie missing)")
        return await run_simulated_scrape(industry, limit, campaign_id, location)
        
    return await run_playwright_scrape(cookie, industry, limit, campaign_id, location)


async def run_playwright_scrape(cookie: str, industry: str, limit: int, campaign_id: Optional[str] = None, location: Optional[str] = None) -> Dict[str, Any]:
    """Scrape real LinkedIn results using Playwright browser automation"""
    scraped_leads = []
    errors_count = 0
    
    try:
        async with async_playwright() as p:
            # Launch headless browser
            browser = await p.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome")
            context = await browser.new_context()
            
            # Inject session cookie
            await context.add_cookies([{
                "name": "li_at",
                "value": cookie,
                "domain": ".www.linkedin.com",
                "path": "/"
            }])
            
            page = await context.new_page()
            
            # Format search query: Owner/Founder/CEO + Industry + Location
            search_query = f"Owner Founder CEO {industry}"
            if location:
                search_query += f" {location}"
            encoded_query = search_query.replace(" ", "%20")
            
            # Base LinkedIn People Search URL
            search_url = f"https://www.linkedin.com/search/results/people/?keywords={encoded_query}&origin=GLOBAL_SEARCH_HEADER"
            
            db = SessionLocal()
            try:
                current_page = 1
                while len(scraped_leads) < limit:
                    url_to_fetch = f"{search_url}&page={current_page}"
                    logger.info("Fetching search results page", page=current_page, url=url_to_fetch)
                    
                    await page.goto(url_to_fetch, timeout=30000)
                    
                    # Wait for results or empty state
                    try:
                        # Wait for anchor tags pointing to profiles
                        await page.wait_for_selector("a[href*='/in/']", timeout=10000)
                    except Exception:
                        # Check if we got redirected to auth/login because of invalid cookie
                        if "login" in page.url or "auth" in page.url or await page.query_selector("input[id='username']"):
                            raise Exception("LinkedIn session cookie (li_at) is invalid or expired. You have been redirected to the login page.")
                            
                        logger.info("No search result selector found on this page. Ending pagination loop.")
                        break
                        
                    # Extract list of search result items
                    links = await page.query_selector_all("a[href*='/in/']")
                    if not links:
                        logger.info("Search result container empty. Ending loop.")
                        break
                        
                    for link in links:
                        if len(scraped_leads) >= limit:
                            break
                            
                        try:
                            text = await link.inner_text()
                            if not text or len(text.strip()) < 20 or "•" not in text:
                                continue
                                
                            profile_url = await link.get_attribute("href")
                            if not profile_url:
                                continue
                            # Clean up tracking params
                            profile_url = profile_url.split("?")[0]
                            
                            lines = [l.strip() for l in text.split("\n") if l.strip()]
                            if len(lines) < 3:
                                continue
                                
                            # 1. Full Name
                            full_name = lines[0].replace('•', '').strip()
                            
                            # Skip outbound links out of linkedin or premium tags
                            if "linkedin member" in full_name.lower() or "premium" in full_name.lower():
                                continue
                                
                            # 2. Headline / Job Title & Location
                            if '•' in lines[1]:
                                headline = lines[2]
                                location = lines[3] if len(lines) > 3 else ""
                            else:
                                headline = lines[1]
                                location = lines[2] if len(lines) > 2 else ""
                            
                            # Extract company name from headline
                            business_name = f"{industry.capitalize()} Company"
                            if " at " in headline:
                                business_name = headline.split(" at ")[-1].strip()
                            elif " @ " in headline:
                                business_name = headline.split(" @ ")[-1].strip()
                                
                            # De-duplicate check
                            existing = db.query(Lead).filter(Lead.linkedin_url == profile_url, Lead.is_active == True).first()
                            if existing:
                                continue
                                
                            # Save to Database
                            lead = Lead(
                                full_name=full_name,
                                business_name=business_name[:200],
                                business_type=industry,
                                phone="+1000000000",  # Placeholder phone
                                city=location.split(",")[0].strip() if "," in location else location[:100],
                                state=location.split(",")[-1].strip() if "," in location else None,
                                linkedin_url=profile_url,
                                campaign_id=uuid.UUID(campaign_id) if campaign_id else None,
                                source="linkedin_scraper",
                                status="pending"
                            )
                            db.add(lead)
                            db.flush() # get generated ID
                            
                            scraped_leads.append({
                                "id": str(lead.id),
                                "full_name": lead.full_name,
                                "business_name": lead.business_name,
                                "linkedin_url": lead.linkedin_url,
                                "status": "scraped"
                            })
                            
                        except Exception as item_err:
                            logger.error("Error parsing search result item", error=str(item_err))
                            errors_count += 1
                            
                    db.commit()
                    
                    # Next page scroll delay
                    await asyncio.sleep(2.0)
                    current_page += 1
                    
            finally:
                db.close()
                
            await browser.close()
            
    except Exception as e:
        logger.error("Fatal exception during Playwright search scraping", error=str(e))
        return {"success": False, "scraped": len(scraped_leads), "errors": 1, "results": scraped_leads, "error_detail": str(e)}

    return {
        "success": True,
        "scraped": len(scraped_leads),
        "errors": errors_count,
        "results": scraped_leads
    }


async def run_simulated_scrape(industry: str, limit: int, campaign_id: Optional[str] = None, location: Optional[str] = None) -> Dict[str, Any]:
    """Generates mock industry leads when Playwright is unavailable"""
    import random
    
    # Mock database profiles mapping based on input industry
    first_names = ["John", "Sarah", "Michael", "Emily", "David", "Jessica", "James", "Amanda", "Robert", "Ashley"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia", "Rodriguez", "Wilson"]
    
    cities = ["New York", "Chicago", "Los Angeles", "Houston", "Miami", "Dallas", "Atlanta", "Seattle", "Boston", "Denver"]
    states = ["NY", "IL", "CA", "TX", "FL", "TX", "GA", "WA", "MA", "CO"]
    
    scraped_leads = []
    db = SessionLocal()
    
    try:
        for i in range(limit):
            # Formulate mock details
            f_name = random.choice(first_names)
            l_name = random.choice(last_names)
            full_name = f"{f_name} {l_name}"
            
            loc_idx = random.randint(0, len(cities) - 1)
            city = cities[loc_idx]
            state = states[loc_idx]
            
            business_types = {
                "automotive": ["Auto Parts", "Car dealership", "Motors", "Tuning Shop", "Car Care Center"],
                "dentist": ["Dental Care", "Family Dental", "Orthodontics Clinic", "Smile Center", "Dentistry"],
                "restaurant": ["Bistro", "Steakhouse", "Diner", "Pizzeria", "Cafe Bar"],
                "salon": ["Beauty Salon", "Barber Shop", "Hair studio", "Nail Spa", "Cosmetics Hub"]
            }
            
            ind_category = industry.lower()
            biz_prefix = f"{full_name}'s"
            biz_suffix = random.choice(business_types.get(ind_category, [f"{industry.capitalize()} Services", f"{industry.capitalize()} Corp"]))
            business_name = f"{biz_prefix} {biz_suffix}"
            
            profile_url = f"https://www.linkedin.com/in/{f_name.lower()}-{l_name.lower()}-{uuid.uuid4().hex[:6]}"
            
            # Check for existing profile url in DB
            existing = db.query(Lead).filter(Lead.linkedin_url == profile_url, Lead.is_active == True).first()
            if existing:
                continue
                
            lead = Lead(
                full_name=full_name,
                business_name=business_name,
                business_type=industry,
                phone=f"+1{random.randint(100, 999)}555{random.randint(1000, 9999)}",
                city=city,
                state=state,
                linkedin_url=profile_url,
                campaign_id=uuid.UUID(campaign_id) if campaign_id else None,
                source="linkedin_scraper_simulated",
                status="pending"
            )
            db.add(lead)
            db.flush()
            
            scraped_leads.append({
                "id": str(lead.id),
                "full_name": lead.full_name,
                "business_name": lead.business_name,
                "linkedin_url": lead.linkedin_url,
                "status": "scraped_simulated"
            })
            
        db.commit()
    except Exception as e:
        logger.error("Error during simulated scrape", error=str(e))
        db.rollback()
    finally:
        db.close()
        
    return {
        "success": True,
        "scraped": len(scraped_leads),
        "errors": 0,
        "results": scraped_leads
    }
