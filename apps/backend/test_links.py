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
        
        links = await page.query_selector_all("a[href*='/in/']")
        for link in links:
            text = await link.inner_text()
            if text and len(text.strip()) > 50:
                print("---")
                print(repr(text))
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
