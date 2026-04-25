import asyncio
import os
from playwright.async_api import async_playwright

CHROME_PROFILE_PATH = os.path.expanduser("~/Library/Application Support/Google/Chrome")

async def debug_substack():
    async with async_playwright() as p:
        try:
            # Reusing persistent context
            context = await p.chromium.launch_persistent_context(
                user_data_dir=CHROME_PROFILE_PATH,
                headless=True,
                args=["--profile-directory=Default"]
            )
            page = await context.new_page()
            print("Navigating to Substack...")
            await page.goto("https://funsizedatabytes.substack.com/publish/stats", wait_until="networkidle")
            
            # Take a screenshot to see what's happening
            await page.screenshot(path="substack_debug.png")
            print("Screenshot saved to substack_debug.png")
            
            # Print page title
            print(f"Page title: {await page.title()}")
            
            # Check for common selectors
            selectors = [".publish-posts-table", ".stats-table", "table", ".posts-list"]
            for s in selectors:
                exists = await page.query_selector(s)
                print(f"Selector '{s}' exists: {exists is not None}")
                
            await context.close()
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_substack())
