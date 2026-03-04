"""
Notion integration — pushes agent drafts to a review database.
"""

import os
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

SETUP_INSTRUCTIONS = """
╔══════════════════════════════════════════════════════════════════╗
║              RC Dev — Notion Setup Instructions                  ║
╚══════════════════════════════════════════════════════════════════╝

═══════════════════════════════════
DATABASE 1: Draft Review Queue
═══════════════════════════════════

STEP 1: Create a Notion Integration (one-time)
  → Go to: https://www.notion.so/my-integrations
  → Click "New integration"
  → Name it: "RC Dev"
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

STEP 3: Share with your integration
  → Open the database → ··· (top right) → "Add connections" → "RC Dev"

STEP 4: Get the Database ID
  → Open the database in browser; URL: notion.so/workspace/XXXXXXXX...?v=...
  → Copy the 32-char ID between the last / and the ?
  → Add to .env: NOTION_DATABASE_ID=xxxxxxxx...

STEP 5: Verify
  → Run: python -m src.cli draft --channel twitter --topic "test"
  → A new row should appear in Notion with Status = "Pending Review"

═══════════════════════════════════
DATABASE 2: Growth Experiments
═══════════════════════════════════

STEP 1: Create the Experiments Database
  → In Notion, create a new page and add a full-page database
  → Name it: "RC Dev — Growth Experiments"
  → Add these properties (exact names matter):
      • Title        (default — keep as-is)
      • Hypothesis   (type: Text)
      • Channel      (type: Select) options: twitter, stackoverflow, blog, reddit, discord, general
      • Content Type (type: Select) options: A/B Test, SEO Content, Community Campaign, Paywall Experiment
      • Status       (type: Select) options: Planned, Running, Complete, Cancelled
      • Start Date   (type: Date)
      • Results      (type: Text)
      • Learnings    (type: Text)
      • Draft ID     (type: Text)

STEP 2: Share with your integration
  → Open the database → ··· (top right) → "Add connections" → "RC Dev"

STEP 3: Get the Database ID
  → Copy the 32-char ID from the URL
  → Add to .env: NOTION_EXPERIMENTS_DB_ID=xxxxxxxx...

STEP 4: Verify
  → Run: python -m src.cli experiment --title "Test" --hypothesis "Test" --channel twitter

═══════════════════════════════════
DATABASE 3: Product Feedback
═══════════════════════════════════

STEP 1: Create the Feedback Database
  → In Notion, create a new page and add a full-page database
  → Name it: "RC Dev — Product Feedback"
  → Add these properties (exact names matter):
      • Title          (default — keep as-is)
      • Category       (type: Select) options: Doc Gap, Feature Request, UX Friction, Community Trend
      • Priority       (type: Select) options: High, Medium, Low
      • Evidence       (type: Text)
      • Recommendation (type: Text)
      • Status         (type: Select) options: New, Reviewed, Actioned
      • Week           (type: Date)
      • Source Channels (type: Text)

STEP 2: Share with your integration
  → Open the database → ··· (top right) → "Add connections" → "RC Dev"

STEP 3: Get the Database ID
  → Copy the 32-char ID from the URL
  → Add to .env: NOTION_FEEDBACK_DB_ID=xxxxxxxx...

STEP 4: Verify
  → Run: python -m src.cli feedback --lookback 30
  → Feedback items should appear in Notion

═══════════════════════════════════
.env Summary
═══════════════════════════════════

  ANTHROPIC_API_KEY=sk-ant-...
  NOTION_API_KEY=secret_...
  NOTION_DATABASE_ID=...         # Draft Review Queue
  NOTION_EXPERIMENTS_DB_ID=...   # Growth Experiments
  NOTION_FEEDBACK_DB_ID=...      # Product Feedback
  OPERATOR_NAME=Rashad Gaines
"""


def print_setup_instructions() -> None:
    print(SETUP_INSTRUCTIONS)


def _content_blocks(text: str) -> list[dict]:
    """Split text into Notion paragraph blocks, respecting the 2000-char limit."""
    chunk_size = 1999
    blocks = []
    for i in range(0, len(text), chunk_size):
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"text": {"content": text[i:i + chunk_size]}}]
            },
        })
    return blocks or [{"object": "block", "type": "paragraph",
                       "paragraph": {"rich_text": [{"text": {"content": ""}}]}}]


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

    title = f"[{draft.channel.upper()}] {draft.topic}"[:200]

    children = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": "Draft Content"}}]},
        }
    ] + _content_blocks(draft.content)

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
        children=children,
    )

    page_url = page.get("url", "")
    return page_url
