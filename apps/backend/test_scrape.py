import asyncio
from app.services.linkedin_scraper import scrape_linkedin_leads
from app.core.config import get_settings

async def main():
    print(get_settings().LINKEDIN_SESSION_COOKIE)
    res = await scrape_linkedin_leads("automotive", limit=5)
    print("Scrape Result:", res)

asyncio.run(main())
