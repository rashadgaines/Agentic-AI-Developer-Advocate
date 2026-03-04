"""
Notion integration — pushes product feedback items to a tracking database.
"""

import os
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()


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


def push_feedback(item: dict) -> str | None:
    """
    Push a product feedback item to the Notion feedback database.

    item keys:
      title, category, priority, evidence, recommendation,
      status, week, source_channels

    Returns the Notion page URL if successful, None otherwise.
    """
    api_key = os.getenv("NOTION_API_KEY")
    db_id = os.getenv("NOTION_FEEDBACK_DB_ID")

    if not api_key or not db_id:
        print(
            "\n⚠️  Feedback DB not configured. Logged locally only.\n"
            "   Run `python -m src.cli setup-notion` for setup instructions.\n"
        )
        return None

    client = Client(auth=api_key)

    title = item.get("title", "Untitled Feedback")[:200]
    category = item.get("category", "Community Trend")
    priority = item.get("priority", "Medium")
    evidence = item.get("evidence", "")
    recommendation = item.get("recommendation", "")
    status = item.get("status", "New")
    week = item.get("week")
    source_channels = item.get("source_channels", "")

    children = []
    if evidence:
        children += [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "Evidence"}}]},
            }
        ] + _content_blocks(evidence)
    if recommendation:
        children += [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "Recommendation"}}]},
            }
        ] + _content_blocks(recommendation)

    properties = {
        "title": {
            "title": [{"text": {"content": title}}]
        },
        "Category": {
            "select": {"name": category}
        },
        "Priority": {
            "select": {"name": priority}
        },
        "Status": {
            "select": {"name": status}
        },
        "Evidence": {
            "rich_text": [{"text": {"content": evidence[:2000]}}]
        },
        "Recommendation": {
            "rich_text": [{"text": {"content": recommendation[:2000]}}]
        },
        "Source Channels": {
            "rich_text": [{"text": {"content": source_channels[:2000]}}]
        },
    }

    if week:
        properties["Week"] = {"date": {"start": week}}

    page = client.pages.create(
        parent={"database_id": db_id},
        properties=properties,
        children=children if children else _content_blocks("No additional notes."),
    )

    return page.get("url", "")
