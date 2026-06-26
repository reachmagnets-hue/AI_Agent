import asyncio
from playwright.async_api import async_playwright
from app.core.config import get_settings

async def main():
    cookie = get_settings().LINKEDIN_SESSION_COOKIE
    cookie_str = cookie or ""
    print("Using cookie:", cookie_str[:10] + "..." + cookie_str[-10:])
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome")
        context = await browser.new_context()
        
        await context.add_cookies([{
            "name": "li_at",
            "value": cookie or "",
            "domain": ".www.linkedin.com",
            "path": "/"
        }])
        
        page = await context.new_page()
        search_url = "https://www.linkedin.com/search/results/people/?keywords=Owner&origin=GLOBAL_SEARCH_HEADER"
        print("Navigating to:", search_url)
        await page.goto(search_url)
        
        # Wait a bit for page to load completely or redirect
        await asyncio.sleep(5)
        
        screenshot_path = "/home/chetan-patil/.gemini/antigravity-ide/brain/89d244fc-00b5-491e-b115-1b7eb370cf23/linkedin_screenshot.png"
        await page.screenshot(path=screenshot_path)
        print("Current URL after navigation:", page.url)
        print(f"Screenshot saved to {screenshot_path}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
