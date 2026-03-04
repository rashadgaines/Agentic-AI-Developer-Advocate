"""
RC Dev agent — drafts developer content using Claude + RAG-grounded context.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

import anthropic
from dotenv import load_dotenv

from src.agent.persona import AGENT_NAME, build_system_prompt
from src.rag import retriever

load_dotenv()

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 2048


@dataclass
class Draft:
    id: str
    channel: str
    topic: str
    content: str
    confidence: str          # HIGH | MEDIUM | LOW
    sources: list[str]
    review_flags: list[str]
    timestamp: str
    raw_response: str
    rag_chunks_used: int = 0
    operator_notes: str = ""
    status: str = "PENDING REVIEW"


def _extract_metadata(response_text: str) -> dict:
    """Parse the REVIEW METADATA block appended by the agent."""
    import re
    confidence = "MEDIUM"
    sources = []
    flags = []

    conf_match = re.search(r"Confidence:\s*(HIGH|MEDIUM|LOW)", response_text, re.I)
    if conf_match:
        confidence = conf_match.group(1).upper()

    sources_match = re.search(r"Sources cited:\s*(.+?)(?:\n|$)", response_text, re.I)
    if sources_match:
        raw = sources_match.group(1).strip()
        if raw.lower() != "none":
            sources = [s.strip() for s in re.split(r"[,;]", raw) if s.strip()]

    flags_match = re.search(r"Review flags:\s*(.+?)(?:\n|$)", response_text, re.I)
    if flags_match:
        raw = flags_match.group(1).strip()
        if raw.lower() != "none":
            flags = [f.strip() for f in re.split(r"[,;]", raw) if f.strip()]

    return {"confidence": confidence, "sources": sources, "flags": flags}


class RCAdvocate:
    def __init__(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not set. Add it to your .env file."
            )
        self.client = anthropic.Anthropic(api_key=api_key)

    def draft(
        self,
        topic: str,
        channel: str = "general",
        extra_context: str = "",
    ) -> Draft:
        """
        Generate a draft for the given topic and channel.
        Retrieves relevant RC doc chunks first, then calls Claude.
        """
        # RAG retrieval
        rag_results = []
        try:
            rag_results = retriever.retrieve(topic, top_k=5)
            doc_context = retriever.format_context(rag_results)
        except FileNotFoundError:
            doc_context = (
                "No local documentation index found. "
                "Run `python -m src.cli ingest` to build it. "
                "Proceeding with general knowledge."
            )

        # Build user message
        user_message = f"""CONTENT BRIEF
Channel: {channel}
Topic: {topic}
{f"Additional context: {extra_context}" if extra_context else ""}

DOCUMENTATION CONTEXT (from RevenueCat docs — use this to ground your response):
{doc_context}

Draft the content now. Follow all formatting and review metadata instructions from your system prompt."""

        system_prompt = build_system_prompt(channel)

        # Call Claude
        message = self.client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_response = message.content[0].text
        metadata = _extract_metadata(raw_response)

        draft_id = f"{channel}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        return Draft(
            id=draft_id,
            channel=channel,
            topic=topic,
            content=raw_response,
            confidence=metadata["confidence"],
            sources=metadata["sources"],
            review_flags=metadata["flags"],
            timestamp=datetime.now(timezone.utc).isoformat(),
            raw_response=raw_response,
            rag_chunks_used=len(rag_results),
        )
