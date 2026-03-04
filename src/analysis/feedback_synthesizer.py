"""
Feedback synthesizer — reads the audit log and uses Claude to produce
structured product feedback items for RevenueCat.
"""

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

LOG_FILE = Path("logs/audit.jsonl")
MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = (
    "You are RC Dev's product feedback synthesizer. "
    "Given patterns observed in developer community interactions, "
    "write concise, actionable product feedback items for RevenueCat. "
    "Each item must be specific and evidence-based — no vague generalities. "
    "Respond only with valid JSON."
)


def _load_records(lookback_days: int) -> list[dict]:
    """Load audit log records within the lookback window."""
    if not LOG_FILE.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    records = []

    with open(LOG_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if record.get("event") != "draft_created":
                    continue
                ts = record.get("timestamp", "")
                record_time = datetime.fromisoformat(ts)
                if record_time >= cutoff:
                    records.append(record)
            except (json.JSONDecodeError, ValueError):
                continue

    return records


def _identify_patterns(records: list[dict]) -> list[dict]:
    """
    Group records into patterns for feedback synthesis.

    Returns a list of pattern dicts:
      { topic_group, category, priority, channels, count, confidence_levels, flags }
    """
    if not records:
        return []

    # Group by topic (normalized)
    topic_groups: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        key = r.get("topic", "unknown").lower().strip()
        topic_groups[key].append(r)

    patterns = []
    for topic, group in topic_groups.items():
        channels = list({r.get("channel", "general") for r in group})
        confidence_levels = [r.get("confidence", "MEDIUM") for r in group]
        all_flags = [flag for r in group for flag in r.get("review_flags", [])]
        count = len(group)

        # Determine category and priority
        has_low = "LOW" in confidence_levels
        has_flags = bool(all_flags)

        if has_low:
            category = "Doc Gap"
            priority = "High" if count >= 2 else "Medium"
        elif count >= 3:
            category = "Community Trend"
            priority = "High"
        elif has_flags:
            category = "UX Friction"
            priority = "Medium"
        else:
            # Single mid-confidence topic — only include if it showed up 2+ times
            if count < 2:
                continue
            category = "Community Trend"
            priority = "Low"

        patterns.append({
            "topic_group": topic,
            "category": category,
            "priority": priority,
            "channels": channels,
            "count": count,
            "confidence_levels": confidence_levels,
            "flags": all_flags,
        })

    # Sort: High priority first, then by count descending
    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    patterns.sort(key=lambda p: (priority_order.get(p["priority"], 3), -p["count"]))

    return patterns


def _synthesize_with_claude(patterns: list[dict], week: str) -> list[dict]:
    """Call Claude to write title, evidence, and recommendation for each pattern."""
    if not patterns:
        return []

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set.")

    client = anthropic.Anthropic(api_key=api_key)

    pattern_text = json.dumps(patterns, indent=2)

    user_message = f"""Here are developer interaction patterns observed this week (week of {week}):

{pattern_text}

For each pattern, write a product feedback item as a JSON object with these exact keys:
- "title": one-sentence name for the feedback item (max 100 chars)
- "category": copy exactly from the pattern's "category" field
- "priority": copy exactly from the pattern's "priority" field
- "evidence": 2-3 sentences describing what the audit data shows. Be specific.
- "recommendation": 1-2 sentences on what RevenueCat should do about it.
- "source_channels": comma-separated list of channels where this appeared

Respond with a JSON array of objects only. No markdown, no explanation."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]

    items = json.loads(raw)

    week_date = week  # ISO date string

    for item in items:
        item["status"] = "New"
        item["week"] = week_date

    return items


def synthesize(lookback_days: int = 7) -> list[dict]:
    """
    Read the audit log and synthesize product feedback items.

    Returns a list of dicts ready for notion_feedback.push_feedback().
    """
    records = _load_records(lookback_days)

    if not records:
        print(f"  No draft records found in the last {lookback_days} days.")
        return []

    print(f"  Analyzing {len(records)} draft records...")
    patterns = _identify_patterns(records)

    if not patterns:
        print("  No significant patterns identified.")
        return []

    print(f"  Found {len(patterns)} pattern(s). Synthesizing with Claude...")
    week = datetime.now(timezone.utc).date().isoformat()
    items = _synthesize_with_claude(patterns, week)

    return items


def synthesize_from_text(audit_summary: str) -> list[dict]:
    """
    Synthesize feedback from a pre-formatted audit summary string.
    Useful for testing without a live audit log.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set.")

    client = anthropic.Anthropic(api_key=api_key)
    week = datetime.now(timezone.utc).date().isoformat()

    user_message = f"""Here is a summary of developer interactions observed this week (week of {week}):

{audit_summary}

Write 2-4 product feedback items as a JSON array. Each object must have:
- "title": one-sentence name (max 100 chars)
- "category": one of: Doc Gap, Feature Request, UX Friction, Community Trend
- "priority": one of: High, Medium, Low
- "evidence": 2-3 sentences describing the pattern observed
- "recommendation": 1-2 sentences on what RevenueCat should do
- "source_channels": comma-separated channels where this appeared
- "status": "New"
- "week": "{week}"

Respond with JSON array only. No markdown, no explanation."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]

    return json.loads(raw)
