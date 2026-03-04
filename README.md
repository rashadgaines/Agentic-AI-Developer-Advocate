# RC Dev — RevenueCat AI Developer Advocate Agent

An AI developer advocate that drafts content grounded in RevenueCat's public documentation, routes every draft through a Notion review queue for human approval, and logs a full audit trail of every action.

**Operator:** Rashad Gaines
**LLM:** Claude claude-sonnet-4-20250514 (Anthropic)
**RAG:** docs.revenuecat.com → FAISS vector index

---

## Quick Start

```bash
# 1. Setup
bash setup.sh
source .venv/bin/activate

# 2. Add API keys
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY and Notion credentials

# 3. Scrape RC docs + build vector index
python -m src.cli ingest

# 4. Generate a draft
python -m src.cli draft --channel twitter --topic "5 mistakes devs make with RC subscriptions"

# 5. Generate all 5 portfolio samples
python -m src.cli portfolio
```

---

## Commands

| Command | Description |
|---------|-------------|
| `python -m src.cli ingest` | Scrape RC docs and build FAISS index |
| `python -m src.cli draft --channel <ch> --topic <t>` | Generate a content draft |
| `python -m src.cli setup-notion` | Print Notion setup instructions |
| `python -m src.cli portfolio` | Generate all 5 portfolio samples |

**Channels:** `twitter`, `stackoverflow`, `blog`, `reddit`, `discord`, `general`

---

## Architecture

```
src/
├── agent/
│   ├── persona.py        # System prompt, voice, scope constraints
│   └── rc_advocate.py    # Agent class (Claude API + RAG)
├── rag/
│   ├── scraper.py        # Crawl docs.revenuecat.com
│   ├── embedder.py       # Chunk + FAISS index
│   └── retriever.py      # Query interface
├── pipeline/
│   ├── notion_queue.py   # Push drafts to Notion DB
│   └── logger.py         # JSONL audit trail
└── cli.py                # Click CLI entry point
```

---

## Content Pipeline

```
[Agent drafts]
     ↓
[Auto quality check: confidence score + source citation + review flags]
     ↓
[Notion "Pending Review" queue]
     ↓
[Operator reviews — approves, edits, or rejects]
     ↓
[Publish to channel]
```

No content is published without operator approval. Every step is logged.

---

## Notion Setup

```bash
python -m src.cli setup-notion
```

Prints step-by-step instructions for creating the Notion integration and database.

Required database properties:
- `Title` (default)
- `Channel` (Select)
- `Status` (Select: Pending Review / Approved / Published / Rejected)
- `Confidence` (Select: HIGH / MEDIUM / LOW)
- `Sources` (Text)
- `Review Flags` (Text)
- `Draft ID` (Text)
- `Timestamp` (Date)
- `Operator Notes` (Text)

---

## Environment Variables

```
ANTHROPIC_API_KEY=sk-ant-...
NOTION_API_KEY=secret_...
NOTION_DATABASE_ID=xxxxxxxx...
OPERATOR_NAME=Rashad Gaines
```

---

## Portfolio

See `portfolio/` for 5 demo outputs showing the full pipeline:

1. `01_twitter_thread.md` — Twitter thread: mistakes devs make with RC
2. `02_stack_overflow.md` — SO answer: offerings returning nil
3. `03_blog_post.md` — Blog: StoreKit 2 vs RevenueCat
4. `04_reddit_comment.md` — Reddit: subscription restore logic
5. `05_discord_faq.md` — Discord FAQ: nil offering on first launch

Each file includes: input brief → raw draft → editorial notes → final version space.

---

## Docs

- `docs/system_prompt.md` — Annotated system prompt explaining each section
- `docs/operator_framework.md` — Accountability structure, incident response, SLA
- `docs/application.md` — The RevenueCat application document
