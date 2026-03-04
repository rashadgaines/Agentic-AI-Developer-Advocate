"""
Audit logger — appends every draft to logs/audit.jsonl for full traceability.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "audit.jsonl"


def log_draft(draft) -> None:
    """Append a draft record to the audit log."""
    LOG_DIR.mkdir(exist_ok=True)

    record = {
        "event": "draft_created",
        "draft_id": draft.id,
        "timestamp": draft.timestamp,
        "operator": os.getenv("OPERATOR_NAME", "unknown"),
        "channel": draft.channel,
        "topic": draft.topic,
        "confidence": draft.confidence,
        "sources": draft.sources,
        "review_flags": draft.review_flags,
        "rag_chunks_used": draft.rag_chunks_used,
        "status": draft.status,
        "content_length": len(draft.content),
    }

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


def log_event(event_type: str, data: dict) -> None:
    """Log an arbitrary event to the audit trail."""
    LOG_DIR.mkdir(exist_ok=True)

    record = {
        "event": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "operator": os.getenv("OPERATOR_NAME", "unknown"),
        **data,
    }

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")
