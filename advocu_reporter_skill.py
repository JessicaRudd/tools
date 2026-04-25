import asyncio
import os
import sys
import argparse
from datetime import datetime
from playwright.async_api import async_playwright
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Configuration
CHROME_PROFILE_PATH = os.path.expanduser("~/Library/Application Support/Google/Chrome")
SUBSTACK_STATS_URL = "https://funsizedatabytes.substack.com/publish/stats"
LINKEDIN_SEARCH_URL = "https://www.linkedin.com/search/results/all/?keywords="
MCP_SERVER_COMMAND = "/Users/jrudd/.nvm/versions/node/v19.6.0/bin/node"
MCP_SERVER_SCRIPT = "/Users/jrudd/Documents/tools/advocu-mcp-server/dist/index.js"
ADVOCU_TOKEN = "59673d2b0103436ba2e09e538ee41dde"
DOCS_DIR = "/Users/jrudd/Documents/tools/advocu-mcp-server/docs"

async def get_substack_metrics(target_title=None, target_url=None):
    print("Gathering Substack metrics...")
    async with async_playwright() as p:
        # Reusing persistent context to stay logged in
        context = await p.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE_PATH,
            headless=True,
            args=["--profile-directory=Default"]
        )
        page = await context.new_page()
        await page.goto(SUBSTACK_STATS_URL, wait_until="networkidle")
        
        # Wait for metrics table
        await page.wait_for_selector(".publish-posts-table")
        
        posts = []
        rows = await page.query_selector_all(".publish-posts-table tr")
        
        # Skip header
        for row in rows[1:]:
            title_el = await row.query_selector(".title-column a")
            if not title_el: continue
            
            title = await title_el.inner_text()
            url = await title_el.get_attribute("href")
            
            # Substack metrics
            views_el = await row.query_selector(".views-column")
            likes_el = await row.query_selector(".likes-column") 
            comments_el = await row.query_selector(".comments-column")

            views = await views_el.inner_text() if views_el else "0"
            likes = await likes_el.inner_text() if likes_el else "0"
            comments = await comments_el.inner_text() if comments_el else "0"
            
            date_el = await row.query_selector(".date-column")
            date_str = await date_el.inner_text() if date_el else datetime.now().strftime("%Y-%m-%d")

            post_data = {
                "title": title.strip(),
                "url": url if url.startswith("http") else f"https://funsizedatabytes.substack.com{url}",
                "views": int(views.replace(",", "").replace(".", "") or 0),
                "likes": int(likes.replace(",", "").replace(".", "") or 0),
                "comments": int(comments.replace(",", "").replace(".", "") or 0),
                "date": date_str.strip()
            }
            posts.append(post_data)
            
            # Break early if we found our target
            if target_title and target_title.lower() in title.lower():
                await context.close()
                return post_data
            if target_url and target_url in url:
                await context.close()
                return post_data
            
            # If no target, return the first one (most recent)
            if not target_title and not target_url:
                await context.close()
                return post_data
        
        await context.close()
        return None

async def get_linkedin_metrics(substack_url):
    print(f"Searching LinkedIn for engagement on: {substack_url}")
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE_PATH,
            headless=True,
            args=["--profile-directory=Default"]
        )
        page = await context.new_page()
        
        search_query = f'"{substack_url}"'
        await page.goto(f"{LINKEDIN_SEARCH_URL}{search_query}", wait_until="networkidle")
        
        # Look for engagement numbers
        try:
            # Note: Selectors for LinkedIn are notoriously flaky, these are best-effort
            # Searching for reaction counts typically found in 'social-details-social-counts'
            await page.wait_for_selector(".search-results-container", timeout=10000)
            
            # Focus on the first relevant post
            reactions_el = await page.query_selector(".social-details-social-counts__social-proof-fallback-number")
            comments_el = await page.query_selector(".social-details-social-counts__comments")
            reposts_el = await page.query_selector(".social-details-social-counts__reposts")
            
            reactions = await reactions_el.inner_text() if reactions_el else "0"
            comments = await comments_el.inner_text() if comments_el else "0"
            reposts = await reposts_el.inner_text() if reposts_el else "0"
            
            # Clean numeric strings
            def clean_num(s):
                return int(''.join(filter(str.isdigit, s)) or 0)

            await context.close()
            return {
                "reactions": clean_num(reactions),
                "comments": clean_num(comments),
                "reposts": clean_num(reposts)
            }
        except:
            print("No LinkedIn engagement found or search failed.")
            await context.close()
            return {"reactions": 0, "comments": 0, "reposts": 0}

async def report_to_advocu(substack_data, linkedin_data, dry_run=False):
    title = substack_data["title"]
    url = substack_data["url"]
    readers = substack_data["views"]
    
    # LinkedIn context for Additional Info
    additional_info = (
        f"Substack Engagement: {substack_data['likes']} likes, {substack_data['comments']} comments.\n"
        f"LinkedIn Engagement: {linkedin_data['reactions']} reactions, "
        f"{linkedin_data['comments']} comments, {linkedin_data['reposts']} reposts."
    )
    
    activity_date = substack_data["date"] # Needs to be YYYY-MM-DD
    # Best-effort date parsing if Substack gives relative dates like "2 days ago"
    # For now assuming we get a parseable date or today
    
    metrics = {
        "title": title,
        "description": f"Post from Fun Size Data Bytes: {title}",
        "activityDate": datetime.now().strftime("%Y-%m-%d"), # Using today as sub date for now
        "contentType": "Articles",
        "metrics": {"readers": readers},
        "activityUrl": url,
        "additionalInfo": additional_info,
        "tags": ["Substack", "Data Science", "Newsletter"]
    }
    
    if dry_run:
        print("\n--- DRY RUN: Advocu Report Data ---")
        import json
        print(json.dumps(metrics, indent=2))
        return "Dry run complete."

    print(f"Submitting to Advocu: {title}")
    server_params = StdioServerParameters(
        command=MCP_SERVER_COMMAND,
        args=[MCP_SERVER_SCRIPT],
        env={
            "ADVOCU_ACCESS_TOKEN": ADVOCU_TOKEN,
            "DOCS_DIR": DOCS_DIR
        }
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("submit_gde_content_creation", metrics)
                return result
    except Exception as e:
        return f"Error reporting to Advocu: {e}"

async def main():
    parser = argparse.ArgumentParser(description="Report Substack/LinkedIn metrics to Advocu.")
    parser.add_argument("--title", help="Filter Substack post by title")
    parser.add_argument("--url", help="Filter Substack post by URL")
    parser.add_argument("--dry-run", action="store_true", help="Print metrics without submitting")
    args = parser.parse_args()

    substack_data = await get_substack_metrics(target_title=args.title, target_url=args.url)
    if not substack_data:
        print("No Substack post found.")
        return

    linkedin_data = await get_linkedin_metrics(substack_data["url"])
    
    result = await report_to_advocu(substack_data, linkedin_data, dry_run=args.dry_run)
    print(f"\nResult: {result}")

if __name__ == "__main__":
    asyncio.run(main())
