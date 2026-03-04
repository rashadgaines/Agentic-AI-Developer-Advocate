"""
Notion integration — pushes growth experiments to a tracking database.
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


def push_experiment(experiment: dict) -> str | None:
    """
    Push a growth experiment to the Notion experiments database.

    experiment keys:
      title, hypothesis, channel, content_type, status,
      start_date, results, learnings, draft_id

    Returns the Notion page URL if successful, None otherwise.
    """
    api_key = os.getenv("NOTION_API_KEY")
    db_id = os.getenv("NOTION_EXPERIMENTS_DB_ID")

    if not api_key or not db_id:
        print(
            "\n⚠️  Experiments DB not configured. Logged locally only.\n"
            "   Run `python -m src.cli setup-notion` for setup instructions.\n"
        )
        return None

    client = Client(auth=api_key)

    title = experiment.get("title", "Untitled Experiment")[:200]
    hypothesis = experiment.get("hypothesis", "")
    channel = experiment.get("channel", "general")
    content_type = experiment.get("content_type", "A/B Test")
    status = experiment.get("status", "Planned")
    start_date = experiment.get("start_date")
    results = experiment.get("results", "")
    learnings = experiment.get("learnings", "")
    draft_id = experiment.get("draft_id", "")

    children = []
    if hypothesis:
        children += [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "Hypothesis"}}]},
            }
        ] + _content_blocks(hypothesis)
    if results:
        children += [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "Results"}}]},
            }
        ] + _content_blocks(results)
    if learnings:
        children += [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "Learnings"}}]},
            }
        ] + _content_blocks(learnings)

    properties = {
        "title": {
            "title": [{"text": {"content": title}}]
        },
        "Channel": {
            "select": {"name": channel}
        },
        "Content Type": {
            "select": {"name": content_type}
        },
        "Status": {
            "select": {"name": status}
        },
        "Hypothesis": {
            "rich_text": [{"text": {"content": hypothesis[:2000]}}]
        },
        "Results": {
            "rich_text": [{"text": {"content": results[:2000]}}]
        },
        "Learnings": {
            "rich_text": [{"text": {"content": learnings[:2000]}}]
        },
        "Draft ID": {
            "rich_text": [{"text": {"content": draft_id[:2000]}}]
        },
    }

    if start_date:
        properties["Start Date"] = {"date": {"start": start_date}}

    page = client.pages.create(
        parent={"database_id": db_id},
        properties=properties,
        children=children if children else _content_blocks("No additional notes."),
    )

    return page.get("url", "")
