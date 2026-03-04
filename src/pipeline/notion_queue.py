"""
Notion integration — pushes agent drafts to a review database.
"""

import os
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

SETUP_INSTRUCTIONS = """
╔══════════════════════════════════════════════════════════════════╗
║         Notion Review Queue — Setup Instructions                 ║
╚══════════════════════════════════════════════════════════════════╝

STEP 1: Create a Notion Integration
  → Go to: https://www.notion.so/my-integrations
  → Click "New integration"
  → Name it: "RC Dev Review Queue"
  → Copy the "Internal Integration Token" (starts with secret_...)
  → Add to .env: NOTION_API_KEY=secret_...

STEP 2: Create the Review Database
  → In Notion, create a new page and add a full-page database
  → Name it: "RC Dev — Draft Review Queue"
  → Add these properties (exact names matter):
      • Title        (default — keep as-is)
      • Channel      (type: Select) options: twitter, stackoverflow, blog, reddit, discord, general
      • Status       (type: Select) options: Pending Review, Approved, Published, Rejected
      • Confidence   (type: Select) options: HIGH, MEDIUM, LOW
      • Sources      (type: Text)
      • Review Flags (type: Text)
      • Draft ID     (type: Text)
      • Timestamp    (type: Date)
      • Operator Notes (type: Text)

STEP 3: Share the database with your integration
  → Open the database page in Notion
  → Click ··· (top right) → "Add connections"
  → Search for "RC Dev Review Queue" and connect it

STEP 4: Get the Database ID
  → Open the database in your browser
  → The URL looks like: notion.so/workspace/XXXXXXXX...?v=...
  → Copy the 32-character ID between the last / and the ?
  → Add to .env: NOTION_DATABASE_ID=xxxxxxxx...

STEP 5: Verify
  → Run: python -m src.cli draft --channel twitter --topic "test"
  → Check Notion — a new row should appear with Status = "Pending Review"
"""


def print_setup_instructions() -> None:
    print(SETUP_INSTRUCTIONS)


def push_draft(draft) -> str | None:
    """
    Push a Draft to the Notion review database.
    Returns the Notion page URL if successful, None otherwise.
    """
    api_key = os.getenv("NOTION_API_KEY")
    db_id = os.getenv("NOTION_DATABASE_ID")

    if not api_key or not db_id:
        print(
            "\n⚠️  Notion not configured. Draft saved locally only.\n"
            "   Run `python -m src.cli setup-notion` for setup instructions.\n"
        )
        return None

    client = Client(auth=api_key)

    sources_str = ", ".join(draft.sources) if draft.sources else "none"
    flags_str = ", ".join(draft.review_flags) if draft.review_flags else "none"

    # Truncate content for Notion title (max 2000 chars for title)
    title = f"[{draft.channel.upper()}] {draft.topic}"[:200]

    page = client.pages.create(
        parent={"database_id": db_id},
        properties={
            "title": {
                "title": [{"text": {"content": title}}]
            },
            "Channel": {
                "select": {"name": draft.channel}
            },
            "Status": {
                "select": {"name": "Pending Review"}
            },
            "Confidence": {
                "select": {"name": draft.confidence}
            },
            "Sources": {
                "rich_text": [{"text": {"content": sources_str[:2000]}}]
            },
            "Review Flags": {
                "rich_text": [{"text": {"content": flags_str[:2000]}}]
            },
            "Draft ID": {
                "rich_text": [{"text": {"content": draft.id}}]
            },
            "Timestamp": {
                "date": {"start": draft.timestamp}
            },
        },
        children=[
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"text": {"content": "Draft Content"}}]
                },
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"text": {"content": draft.content[:2000]}}
                    ]
                },
            },
        ],
    )

    page_url = page.get("url", "")
    return page_url
