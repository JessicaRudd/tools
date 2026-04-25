import asyncio
import os
from playwright.async_api import async_playwright

CHROME_PROFILE_PATH = os.path.expanduser("~/Library/Application Support/Google/Chrome")
DRAFT_URL = "https://funsizedatabytes.substack.com/publish/post/194729823"

BODY_TEXT = """### By Jessica Rudd (Co-written & Automated by Antigravity)

As a Google Developer Expert (GDE), reporting activities is a crucial part of the program. Whether it’s writing articles, speaking at conferences, or mentoring, documentation ensures our impact is recognized. But let’s be honest: manual data entry is a chore.

Last week, during a rapid prototyping session for **Folio**, I decided to solve this. Using **Antigravity** (my AI pair-programmer) and a brilliant MCP server by **Carlos Azaustre**, I built a "Skill" that automates the whole process.

## The Problem: The Reporting Gap

Every time I publish a post on Substack or share it on LinkedIn, I have to manually copy-paste view counts, likes, and links into the Advocu portal. It’s a minor friction point that adds up.

## The Solution: Model Context Protocol (MCP)

The breakthrough came from leveraging the **Model Context Protocol**. I installed the [advocu-mcp-server](https://github.com/carlosazaustre/advocu-mcp-server) created by Carlos Azaustre. This bridge allows an AI agent to communicate directly with the Advocu API.

### 1. Building the Scraper
Antigravity and I developed a Python skill that uses **Playwright** to:
- Navigate to my Substack stats page.
- Search LinkedIn for the article's URL to find engagement (reactions and reposts).

### 2. The Advocu Handshake
Once the metrics are gathered, the script calls the `submit_gde_content_creation` tool. It maps the data to official GDE categories like [Google Cloud](https://cloud.google.com/?utm_campaign=deveco_gdemembers&utm_source=deveco) and [Gemini](https://deepmind.google/technologies/gemini/?utm_campaign=deveco_gdemembers&utm_source=deveco).

## The Result: One-Click Submission

I tested it live on my recent post, *"Zero to V1: Rapid Prototyping with Gemini"*. Within seconds, the skill gathered the stats (46 views on Substack, several reactions on LinkedIn) and successfully created the activity draft in Advocu.

## Why This Matters

Automation isn't just about saving time; it's about accuracy and consistency. By integrating our developer tools with program management APIs, we can spend more time building and less time filling out forms.

Special thanks again to **Carlos Azaustre** for the open-source MCP server that made this possible.

If you’re a GDE or MVP looking to automate your workflow, I highly recommend checking out the [Google Developers Experts](https://developers.google.com/experts?utm_campaign=deveco_gdemembers&utm_source=deveco) program resources and the growing ecosystem of MCP servers.

---
**Tags**: #codeinpublic #automation #gde #GoogleCloud #Gemini

*This post was drafted and published using the Antigravity Substack Automator Skill.*
"""

async def publish_draft():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE_PATH,
            headless=True,
            args=["--profile-directory=Default"]
        )
        page = await context.new_page()
        print(f"Opening draft: {DRAFT_URL}")
        await page.goto(DRAFT_URL, wait_until="networkidle")
        
        # Set Title (just in case)
        await page.fill("#post-title", "Automating My GDE Life: From Manual Entry to One-Click Submission")
        
        # Focus editor body
        # Substack uses a complex editor (often ProseMirror/Tiptap), but we can try to paste
        print("Pasting body text...")
        await page.click(".prose-mirror-editor")
        await page.keyboard.insert_text(BODY_TEXT)
        
        # Upload images
        # We find the file input. Substack often has a hidden one.
        print("Uploading images...")
        hero_path = "/Users/jrudd/.gemini/antigravity/brain/ea34e100-86ae-4cb8-a3ec-7d98b2c7576a/substack_hero_advocu_automation_1776630888119.png"
        code_path = "/Users/jrudd/.gemini/antigravity/brain/ea34e100-86ae-4cb8-a3ec-7d98b2c7576a/advocu_reporter_code_1776630915634.png"
        id_path = "/Users/jrudd/.gemini/antigravity/brain/ea34e100-86ae-4cb8-a3ec-7d98b2c7576a/advocu_submission_id_1776630942030.png"
        
        file_input = page.locator("input[type='file']")
        await file_input.set_input_files([hero_path, code_path, id_path])
        
        # Wait for uploads
        await asyncio.sleep(5)
        
        await page.screenshot(path="substack_publish_confirmation.png")
        print("Confirmation screenshot saved.")
        
        await context.close()

if __name__ == "__main__":
    asyncio.run(publish_draft())
