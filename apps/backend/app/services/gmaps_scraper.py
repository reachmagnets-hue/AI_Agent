import re
import asyncio
import httpx
from urllib.parse import quote_plus, urlparse
from playwright.async_api import async_playwright
from app.core.database import SessionLocal
from app.models.campaign import Campaign
from app.models.lead import Lead
from uuid import uuid4
import structlog

logger = structlog.get_logger(__name__)

from typing import Dict, Any, Optional, List, Set

EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')

def is_valid_social_profile_link(url: str) -> bool:
    """
    Checks if a social media link is a valid profile URL or just a platform/builder template link.
    """
    if not url:
        return False
    url_lower = url.lower().strip()
    
    # Common website builders, templates, or actions to filter out
    blacklist_patterns = [
        "wix.com", "wixpress.com", "shopify.com", "squarespace.com", "wordpress.com", 
        "godaddy.com", "weebly.com", "webflow.com", "envato.com", "themeforest.net",
        "/wix", "/shopify", "/squarespace", "/wordpress", "/godaddy", "/weebly", "/webflow",
        "sharer.php", "share.php", "intent/tweet", "twitter.com/share", "facebook.com/sharer",
        "templates", "theme", "plugin", "widget", "pages/create", "create-a-page",
        "facebook.com/pages/create", "instagram.com/p/", "instagram.com/reel/",
        "instagram.com/stories/", "linkedin.com/shareArticle", "linkedin.com/sharing",
        "youtube.com/embed/", "youtube.com/watch?", "intent/follow"
    ]
    
    if any(pat in url_lower for pat in blacklist_patterns):
        return False
        
    try:
        parsed = urlparse(url_lower)
        path = parsed.path.strip("/")
        # If path is empty, or exactly a platform corporate account name
        if not path or path in [
            "facebook", "instagram", "twitter", "linkedin", "youtube", "pinterest", 
            "wix", "shopify", "squarespace", "wordpress", "godaddy", "weebly", "webflow", "elementor"
        ]:
            return False
            
        # Avoid generic builder paths
        path_parts = path.split("/")
        if path_parts and path_parts[0] in [
            "wix", "shopify", "squarespace", "wordpress", "godaddy", "weebly", "webflow", "elementor"
        ]:
            return False
    except Exception:
        pass
        
    return True

DIRECTORY_RULES = {
    "Yelp": ["yelp.com/biz/"],
    "BBB": ["bbb.org/us/", "bbb.org/ca/"],
    "YellowPages": ["yellowpages.com/", "yp.com/"],
    "Nextdoor": ["nextdoor.com/pages/", "nextdoor.com/biz/"],
    "Trustpilot": ["trustpilot.com/review/"],
    "Angi": ["angi.com/companylist/", "angieslist.com/companylist/"],
    "Houzz": ["houzz.com/pro/", "houzz.com/professionals/"],
    "Thumbtack": ["thumbtack.com/"],
    "HomeAdvisor": ["homeadvisor.com/rated."],
    "Porch": ["porch.com/"],
    "Manta": ["manta.com/c/"],
    "Superpages": ["superpages.com/"],
    "Citysearch": ["citysearch.com/profile/"],
    "EZLocal": ["ezlocal.com/"],
    "Local.com": ["local.com/business/"],
    "MerchantCircle": ["merchantcircle.com/"],
    "Zillow": ["zillow.com/profile/", "zillow.com/professionals/"],
    "Realtor": ["realtor.com/realestateagents/"],
    "Healthgrades": ["healthgrades.com/physician/", "healthgrades.com/group-directory/"],
    "Zocdoc": ["zocdoc.com/doctor/", "zocdoc.com/practice/"],
    "Vitals": ["vitals.com/doctors/"],
    "Avvo": ["avvo.com/attorneys/"],
    "Lawyers.com": ["lawyers.com/"],
    "Justia": ["lawyers.justia.com/lawyer/"],
    "ThomasNet": ["thomasnet.com/profile/"],
    "Kompass": ["kompass.com/c/"],
    "UpCity": ["upcity.com/profiles/"],
    "Capterra": ["capterra.com/p/"],
    "G2": ["g2.com/products/"],
    "Cars.com": ["cars.com/dealers/"],
    "CarGurus": ["cargurus.com/Cars/m-"],
    "DealerRater": ["dealerrater.com/dealer/"],
    "Carwise": ["carwise.com/auto-body-shops/"],
    "Pinterest": ["pinterest.com/"],
    "TikTok": ["tiktok.com/@"]
}

async def find_website_details(url: str) -> Dict[str, Any]:
    """
    Fetches homepage & contact pages to extract emails, social media profile links,
    local directory links (Yelp, BBB, Nextdoor, YellowPages, Angi, etc.), and meta description text.
    """
    results: Dict[str, Any] = {
        "emails": [],
        "facebook_url": None,
        "instagram_url": None,
        "linkedin_url": None,
        "twitter_url": None,
        "youtube_url": None,
        "directories": {},
        "meta_description": None
    }
    if not url:
        return results
    if not url.startswith("http"):
        url = "http://" + url
        
    # Ignore search engines and pure social homepages
    if any(domain in url.lower() for domain in ["google.com", "facebook.com", "instagram.com", "twitter.com"]):
        return results
        
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }) as client:
            res = await client.get(url)
            if res.status_code == 200:
                html = res.text
                
                # 1. Emails
                emails = EMAIL_REGEX.findall(html)
                for email in emails:
                    email_lower = email.lower()
                    if not any(email_lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js", "wixpress.com", "email.com"]):
                        if email not in results["emails"]:
                            results["emails"].append(email)
                            
                # 2. Social & Directory links from hrefs
                all_hrefs = re.findall(r'href=["\'](https?://[^"\']+)["\']', html, re.IGNORECASE)
                for link in all_hrefs:
                    link_clean = link.strip().rstrip('"\'>')
                    link_lower = link_clean.lower()
                    
                    # Social Media
                    if ("facebook.com/" in link_lower or "fb.com/" in link_lower or "fb.me/" in link_lower):
                        if not any(skip in link_lower for skip in ["sharer", "share.php", "dialog", "plugins", "intent"]):
                            if not results["facebook_url"] and is_valid_social_profile_link(link_clean):
                                results["facebook_url"] = link_clean
                    elif "instagram.com/" in link_lower or "instagr.am/" in link_lower:
                        if not any(skip in link_lower for skip in ["/p/", "/reel/", "/explore/", "/stories/"]):
                            if not results["instagram_url"] and is_valid_social_profile_link(link_clean):
                                results["instagram_url"] = link_clean
                    elif "linkedin.com/" in link_lower:
                        if any(k in link_lower for k in ["company", "/in/", "school", "pub", "showcase", "profile"]):
                            if not results["linkedin_url"] and is_valid_social_profile_link(link_clean):
                                results["linkedin_url"] = link_clean
                    elif "twitter.com/" in link_lower or "x.com/" in link_lower:
                        if not any(skip in link_lower for skip in ["intent/", "share?", "widgets"]):
                            if not results["twitter_url"] and is_valid_social_profile_link(link_clean):
                                results["twitter_url"] = link_clean
                    elif "youtube.com/" in link_lower or "youtu.be/" in link_lower:
                        if not any(skip in link_lower for skip in ["embed/", "watch?"]):
                            if not results["youtube_url"] and is_valid_social_profile_link(link_clean):
                                results["youtube_url"] = link_clean
                                
                    # Directory Profiles Scanning
                    for d_name, d_pats in DIRECTORY_RULES.items():
                        if d_name not in results["directories"]:
                            for pat in d_pats:
                                if pat in link_lower and is_valid_social_profile_link(link_clean):
                                    results["directories"][d_name] = link_clean
                                    break
                            
                # 3. Meta Description (About Shop summary)
                desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                if not desc_match:
                    desc_match = re.search(r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                if desc_match:
                    results["meta_description"] = desc_match.group(1).strip()
                    
                # 4. Discover contact pages for more emails & socials
                contact_links = []
                hrefs = re.findall(r'href=["\'](https?://[^"\']+|/[^"\']+)["\']', html, re.IGNORECASE)
                from urllib.parse import urljoin
                for href in hrefs:
                    href_lower = href.lower()
                    if any(word in href_lower for word in ["contact", "about", "connect", "reach"]):
                        full_link = urljoin(url, href)
                        if full_link not in contact_links and full_link != url:
                            contact_links.append(full_link)
                            
                for contact_url in contact_links[:2]:
                    try:
                        c_res = await client.get(contact_url, timeout=5.0)
                        if c_res.status_code == 200:
                            c_html = c_res.text
                            c_emails = EMAIL_REGEX.findall(c_html)
                            for email in c_emails:
                                email_lower = email.lower()
                                if not any(email_lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js", "wixpress.com", "email.com"]):
                                    if email not in results["emails"]:
                                        results["emails"].append(email)
                                        
                            c_hrefs = re.findall(r'href=["\'](https?://[^"\']+)["\']', c_html, re.IGNORECASE)
                            for link in c_hrefs:
                                link_clean = link.strip().rstrip('"\'>')
                                link_lower = link_clean.lower()
                                if ("facebook.com/" in link_lower or "fb.com/" in link_lower) and not results["facebook_url"]:
                                    if not any(skip in link_lower for skip in ["sharer", "share.php", "dialog"]):
                                        if is_valid_social_profile_link(link_clean):
                                            results["facebook_url"] = link_clean
                                elif ("instagram.com/" in link_lower or "instagr.am/" in link_lower) and not results["instagram_url"]:
                                    if not any(skip in link_lower for skip in ["/p/", "/reel/"]):
                                        if is_valid_social_profile_link(link_clean):
                                            results["instagram_url"] = link_clean
                                elif "linkedin.com/" in link_lower and not results["linkedin_url"]:
                                    if is_valid_social_profile_link(link_clean):
                                        results["linkedin_url"] = link_clean
                                elif ("twitter.com/" in link_lower or "x.com/" in link_lower) and not results["twitter_url"]:
                                    if is_valid_social_profile_link(link_clean):
                                        results["twitter_url"] = link_clean
                                elif ("youtube.com/" in link_lower or "youtu.be/" in link_lower) and not results["youtube_url"]:
                                    if is_valid_social_profile_link(link_clean):
                                        results["youtube_url"] = link_clean
                                        
                                for d_name, d_pats in DIRECTORY_RULES.items():
                                    if d_name not in results["directories"]:
                                        for pat in d_pats:
                                            if pat in link_lower and is_valid_social_profile_link(link_clean):
                                                results["directories"][d_name] = link_clean
                                                break
                    except Exception:
                        pass
    except Exception as e:
        logger.debug("Failed to fetch website details", url=url, error=str(e))
    return results

def levenshtein_distance(s1: str, s2: str) -> int:
    """Computes the Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def is_valid_location_match(address: str, target_location: str) -> bool:
    """Always accept valid listings returned by Google Maps search query"""
    return True

async def scrape_gmaps(industry: str, location: str, limit: int = 10, update_callback=None):
    """
    Launches Playwright Chromium browser, searches Google Maps, incrementally scrolls feed,
    clicks cards, enriches details/websites, saves directly to DB, and streams progress live via WebSockets.
    """
    print(f"DEBUG scrape_gmaps: Starting extraction with industry={industry}, location={location}, limit={limit}")
    logger.info("Starting Google Maps extraction", industry=industry, location=location, limit=limit)
    
    # 1. Create or Find Campaign Folder
    db = SessionLocal()
    campaign_name = f"Extracted - {industry.title()} in {location.title()}"
    seen_names: Set[str] = set()
    seen_phones: Set[str] = set()
    seen_websites: Set[str] = set()

    try:
        campaign = db.query(Campaign).filter(Campaign.name == campaign_name).first()
        if not campaign:
            campaign = Campaign(
                id=uuid4(),
                name=campaign_name,
                description=f"Auto-extracted local leads for {industry} in {location}",
                status="inactive",
                calls_per_minute=2,
                max_attempts=3
            )
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
        campaign_id = campaign.id

        # Pre-populate deduplication sets from existing DB leads
        existing_leads = db.query(Lead).filter(Lead.campaign_id == campaign_id).all()
        for el in existing_leads:
            if el.business_name:
                seen_names.add(re.sub(r'\W+', '', str(el.business_name).lower()))
            if el.phone:
                seen_phones.add(re.sub(r'\D+', '', str(el.phone)))
            if el.website:
                c_web = str(el.website).lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
                if c_web:
                    seen_websites.add(c_web)
    finally:
        db.close()
        
    search_query = f"{industry} in {location}"
    search_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"
    
    extracted_count = 0
    processed_card_ids: Set[str] = set()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path="/usr/bin/google-chrome",
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--password-store=basic"
            ]
        )
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()
        
        try:
            logger.info("Navigating to Google Maps search", url=search_url)
            await page.goto(search_url, timeout=60000)
            await page.wait_for_timeout(4000)
            
            feed_selector = "div[role='feed']"
            has_feed = await page.locator(feed_selector).count() > 0
            
            consecutive_no_new = 0
            max_cycles = max(limit * 4, 150)
            cycle = 0
            
            while extracted_count < limit and cycle < max_cycles:
                cycle += 1
                
                # Fetch currently rendered place card links
                cards = await page.locator("a.hfpxzc").all()
                new_card_found = False
                
                for card in cards:
                    if extracted_count >= limit:
                        break
                        
                    try:
                        # Card identification string to prevent re-processing in virtualized list
                        aria_label = await card.get_attribute("aria-label") or ""
                        href = await card.get_attribute("href") or ""
                        card_id = f"{aria_label}_{href[:60]}"
                        
                        if not aria_label or card_id in processed_card_ids:
                            continue
                            
                        processed_card_ids.add(card_id)
                        
                        # Check if listing is a sponsored Ad
                        try:
                            text_content = await card.inner_text()
                            if "Sponsored" in text_content or "Ad" in text_content.split():
                                continue
                        except Exception:
                            pass
                            
                        # Scroll card into view & click
                        await card.scroll_into_view_if_needed()
                        await page.wait_for_timeout(200)
                        await card.click(force=True)
                        await page.wait_for_timeout(1500)
                        
                        # Extract details from details pane
                        name = aria_label
                        phone = ""
                        website = ""
                        address = ""
                        rating = ""
                        gmaps_desc = ""
                        facebook_url = None
                        instagram_url = None
                        linkedin_url = None
                        twitter_url = None
                        youtube_url = None
                        
                        # 1. Phone
                        phone_loc = page.locator("button[data-item-id^='phone:tel:']")
                        if await phone_loc.count() > 0:
                            raw_phone = await phone_loc.first.get_attribute("data-item-id")
                            if raw_phone:
                                phone = raw_phone.replace("phone:tel:", "").strip()
                                
                        # 2. Website
                        web_loc = page.locator("a[data-item-id='authority']")
                        if await web_loc.count() > 0:
                            website = await web_loc.first.get_attribute("href")
                            
                        # 3. Address
                        addr_loc = page.locator("button[data-item-id='address']")
                        if await addr_loc.count() > 0:
                            address = await addr_loc.first.inner_text()
                            
                        # 4. Rating & Reviews
                        rating_loc = page.locator("span[role='img'][aria-label*='star'], span.ceNzKf, div.F7v28c")
                        if await rating_loc.count() > 0:
                            rating = await rating_loc.first.get_attribute("aria-label") or await rating_loc.first.inner_text()
                            
                        # 5. Category / Shop Snippet
                        cat_loc = page.locator("button[jsaction*='category'], button.DkSF2b, div.PYvAId, div.WiI7pd")
                        if await cat_loc.count() > 0:
                            gmaps_desc = await cat_loc.first.inner_text()
                            
                        # 6. Social links on card
                        try:
                            social_links = await page.locator("a[href*='facebook.com'], a[href*='instagram.com'], a[href*='linkedin.com'], a[href*='twitter.com'], a[href*='youtube.com']").all()
                            for s_link in social_links:
                                s_href = await s_link.get_attribute("href")
                                if s_href and is_valid_social_profile_link(s_href):
                                    h_lower = s_href.lower()
                                    if "facebook.com" in h_lower and not facebook_url:
                                        facebook_url = s_href
                                    elif "instagram.com" in h_lower and not instagram_url:
                                        instagram_url = s_href
                                    elif "linkedin.com" in h_lower and not linkedin_url:
                                        linkedin_url = s_href
                                    elif ("twitter.com" in h_lower or "x.com" in h_lower) and not twitter_url:
                                        twitter_url = s_href
                                    elif "youtube.com" in h_lower and not youtube_url:
                                        youtube_url = s_href
                        except Exception:
                            pass
                            
                        # Location matching validation
                        if address and location and not is_valid_location_match(address, location):
                            logger.info("Skipping listing outside target location", name=name, address=address, target_location=location)
                            continue
                            
                        # Deduplication check
                        norm_name = re.sub(r'\W+', '', str(name).lower()) if name else ""
                        clean_phone = re.sub(r'\D+', '', str(phone)) if phone else ""
                        clean_web = str(website).lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/") if website else ""
                        
                        is_duplicate = (norm_name and norm_name in seen_names) or (clean_phone and clean_phone in seen_phones) or (clean_web and clean_web in seen_websites)
                        
                        if is_duplicate:
                            logger.info("Listing already exists in DB, skipping duplicate card", name=name)
                            new_card_found = True
                            continue
                            
                        if norm_name:
                            seen_names.add(norm_name)
                        if clean_phone:
                            seen_phones.add(clean_phone)
                        if clean_web:
                            seen_websites.add(clean_web)
                            
                        # Fast website enrichment (emails, socials, meta summary)
                        email = None
                        if website:
                            try:
                                web_info = await asyncio.wait_for(find_website_details(website), timeout=5.0)
                                if web_info["emails"]:
                                    email = web_info["emails"][0]
                                if not facebook_url and web_info["facebook_url"]:
                                    facebook_url = web_info["facebook_url"]
                                if not instagram_url and web_info["instagram_url"]:
                                    instagram_url = web_info["instagram_url"]
                                if not linkedin_url and web_info["linkedin_url"]:
                                    linkedin_url = web_info["linkedin_url"]
                                if not twitter_url and web_info["twitter_url"]:
                                    twitter_url = web_info["twitter_url"]
                                if not youtube_url and web_info["youtube_url"]:
                                    youtube_url = web_info["youtube_url"]
                                dir_str = ""
                                if web_info.get("directories"):
                                    dir_items = [f"{d_name}: {d_url}" for d_name, d_url in web_info["directories"].items()]
                                    dir_str = "\n[Directories] " + " | ".join(dir_items)
                                if web_info["meta_description"]:
                                    gmaps_desc = f"{gmaps_desc} • {web_info['meta_description']}" if gmaps_desc else web_info['meta_description']
                            except Exception as web_err:
                                logger.debug("Quick website enrichment skipped/timed out", url=website, error=str(web_err))
                        else:
                            dir_str = ""
                                
                        lead_data = {
                            "name": name.strip(),
                            "phone": phone.strip() if phone else None,
                            "website": website.strip() if website else None,
                            "address": address.strip() if address else None,
                            "email": email,
                            "facebook_url": facebook_url,
                            "instagram_url": instagram_url,
                            "linkedin_url": linkedin_url,
                            "twitter_url": twitter_url,
                            "youtube_url": youtube_url,
                            "rating": rating.strip() if rating else None,
                            "description": gmaps_desc.strip() if gmaps_desc else None,
                            "is_duplicate": False
                        }
                        
                        # Save new lead directly to Database
                        db_item = SessionLocal()
                        try:
                            new_lead = Lead(
                                id=uuid4(),
                                full_name=lead_data["name"],
                                business_name=lead_data["name"],
                                phone=lead_data["phone"],
                                email=lead_data["email"],
                                website=lead_data["website"],
                                facebook_url=lead_data["facebook_url"],
                                instagram_url=lead_data["instagram_url"],
                                linkedin_url=lead_data["linkedin_url"],
                                twitter_url=lead_data["twitter_url"],
                                youtube_url=lead_data["youtube_url"],
                                rating=lead_data["rating"],
                                description=lead_data["description"],
                                business_type=industry,
                                campaign_id=campaign_id,
                                source="google_maps_scrape",
                                status="pending",
                                internal_notes=f"Full Address: {lead_data['address'] or 'N/A'}{dir_str}"
                            )
                            db_item.add(new_lead)
                            db_item.commit()
                        except Exception as db_err:
                            logger.error("Failed saving scraped lead to DB", name=lead_data["name"], error=str(db_err))
                        finally:
                            db_item.close()
                            
                        extracted_count += 1
                        new_card_found = True
                        logger.info("Successfully extracted lead", count=extracted_count, name=lead_data["name"])
                        
                        # STREAM LIVE OVER WEBSOCKETS IMMEDIATELY!
                        if update_callback:
                            await update_callback(lead_data, extracted_count, limit)
                            
                    except Exception as card_err:
                        logger.warning("Error processing card", error=str(card_err))
                        
                # Scroll feed down to trigger next batch of virtualized cards
                if has_feed:
                    await page.locator(feed_selector).evaluate("el => el.scrollBy(0, 2500)")
                else:
                    await page.mouse.wheel(0, 2500)
                    
                await page.wait_for_timeout(800)
                
                if not new_card_found:
                    consecutive_no_new += 1
                else:
                    consecutive_no_new = 0
                    
                # Stop if no new cards loaded after 5 scroll attempts or reached end of list
                end_of_results = await page.locator("text=\"You've reached the end of the list.\"").count() > 0
                if end_of_results or consecutive_no_new >= 5:
                    logger.info("Ending extraction feed scroll", total_extracted=extracted_count, end_reached=end_of_results)
                    break
                    
        finally:
            await browser.close()
            
    logger.info("Scraping completed successfully", total_extracted=extracted_count, target_limit=limit)
    return extracted_count

