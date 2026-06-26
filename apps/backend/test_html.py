import asyncio
from playwright.async_api import async_playwright
from app.core.config import get_settings

async def main():
    cookie = get_settings().LINKEDIN_SESSION_COOKIE
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome")
        context = await browser.new_context()
        await context.add_cookies([{"name": "li_at", "value": cookie or "", "domain": ".www.linkedin.com", "path": "/"}])
        page = await context.new_page()
        
        await page.goto("https://www.linkedin.com/search/results/people/?keywords=Owner")
        await asyncio.sleep(5)
        
        # Save HTML to investigate
        html = await page.content()
        with open("linkedin_search.html", "w") as f:
            f.write(html)
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
