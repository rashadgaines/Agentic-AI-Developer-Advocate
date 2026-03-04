"""
RC Dev CLI — entry point for all agent commands.

Usage:
  python -m src.cli ingest
  python -m src.cli draft --channel twitter --topic "your topic"
  python -m src.cli setup-notion
  python -m src.cli portfolio
"""

import json
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

load_dotenv()


@click.group()
def cli():
    """RC Dev — RevenueCat AI Developer Advocate Agent"""
    pass


# ─────────────────────────────────────────────
# INGEST: Scrape + embed RC docs
# ─────────────────────────────────────────────
@cli.command()
@click.option("--max-pages", default=200, help="Max pages to scrape (default: 200)")
@click.option("--skip-scrape", is_flag=True, help="Skip scraping, only rebuild index")
def ingest(max_pages, skip_scrape):
    """Scrape RevenueCat docs and build the vector index."""
    from src.rag.scraper import scrape
    from src.rag.embedder import build_index

    if not skip_scrape:
        click.echo("Step 1/2: Scraping RevenueCat docs...")
        count = scrape(max_pages=max_pages)
        if count == 0:
            click.echo("ERROR: No pages scraped. Check your internet connection.", err=True)
            sys.exit(1)
    else:
        click.echo("Skipping scrape.")

    click.echo("\nStep 2/2: Building vector index...")
    build_index()
    click.echo("\n✓ Ingest complete. Run `python -m src.cli draft` to generate content.")


# ─────────────────────────────────────────────
# DRAFT: Generate a content draft
# ─────────────────────────────────────────────
VALID_CHANNELS = ["twitter", "stackoverflow", "blog", "reddit", "discord", "general"]


@cli.command()
@click.option(
    "--channel",
    required=True,
    type=click.Choice(VALID_CHANNELS),
    help="Target channel for the content",
)
@click.option("--topic", required=True, help="Topic or content brief")
@click.option("--context", default="", help="Optional extra context for the agent")
@click.option("--save", is_flag=True, default=True, help="Save draft locally (default: true)")
@click.option("--no-notion", is_flag=True, help="Skip pushing to Notion")
@click.option(
    "--mode",
    default="review",
    type=click.Choice(["review", "auto"]),
    help="review: all drafts → Notion queue. auto: HIGH confidence + no flags → auto-approved.",
)
def draft(channel, topic, context, save, no_notion, mode):
    """Generate a content draft and route to the review queue."""
    from src.agent.rc_advocate import RCAdvocate
    from src.pipeline import notion_queue, logger

    click.echo(f"\nGenerating {channel} draft: \"{topic}\"")
    click.echo("─" * 60)

    try:
        agent = RCAdvocate()
    except ValueError as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)

    result = agent.draft(topic=topic, channel=channel, extra_context=context)

    # Print to terminal
    click.echo(result.content)
    click.echo("\n" + "─" * 60)
    click.echo(f"Confidence: {result.confidence}")
    click.echo(f"RAG chunks used: {result.rag_chunks_used}")
    if result.review_flags:
        click.echo(f"⚠️  Review flags: {', '.join(result.review_flags)}")
    click.echo(f"Draft ID: {result.id}")

    # Routing logic
    if mode == "auto" and result.confidence == "HIGH" and not result.review_flags:
        result.status = "AUTO-APPROVED"
        result.auto_approved = True
        click.echo("\n✓ AUTO-APPROVED — HIGH confidence, no flags.")
    elif not no_notion:
        click.echo("\nPushing to Notion review queue...")
        notion_url = notion_queue.push_draft(result)
        if notion_url:
            click.echo(f"✓ Notion: {notion_url}")

    # Save locally
    if save:
        out_dir = Path("drafts")
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"{result.id}.json"
        out_path.write_text(json.dumps({
            "id": result.id,
            "channel": result.channel,
            "topic": result.topic,
            "content": result.content,
            "confidence": result.confidence,
            "sources": result.sources,
            "review_flags": result.review_flags,
            "timestamp": result.timestamp,
            "status": result.status,
            "auto_approved": result.auto_approved,
        }, indent=2))
        click.echo(f"Draft saved: {out_path}")

    # Audit log
    logger.log_draft(result)

    click.echo(f"\n✓ Draft complete. Status: {result.status}")


# ─────────────────────────────────────────────
# SETUP-NOTION: Print Notion setup instructions
# ─────────────────────────────────────────────
@cli.command("setup-notion")
def setup_notion():
    """Print step-by-step Notion integration setup instructions."""
    from src.pipeline.notion_queue import print_setup_instructions
    print_setup_instructions()


# ─────────────────────────────────────────────
# PORTFOLIO: Generate all 5 demo samples
# ─────────────────────────────────────────────
PORTFOLIO_BRIEFS = [
    {
        "filename": "01_twitter_thread.md",
        "channel": "twitter",
        "topic": "5 mistakes developers make when implementing RevenueCat subscriptions",
        "label": "Twitter Thread",
    },
    {
        "filename": "02_stack_overflow.md",
        "channel": "stackoverflow",
        "topic": "RevenueCat Purchases.shared.getOfferings returns nil — how to debug",
        "label": "Stack Overflow Answer",
    },
    {
        "filename": "03_blog_post.md",
        "channel": "blog",
        "topic": "StoreKit 2 vs RevenueCat: when to use each and when to use both",
        "label": "Blog Post",
    },
    {
        "filename": "04_reddit_comment.md",
        "channel": "reddit",
        "topic": "Developer asking how to implement subscription restore logic correctly with RevenueCat",
        "label": "Reddit Comment",
    },
    {
        "filename": "05_discord_faq.md",
        "channel": "discord",
        "topic": "Why is my RevenueCat offering showing as nil on first app launch?",
        "label": "Discord FAQ Answer",
    },
]


@cli.command()
@click.option("--no-notion", is_flag=True, help="Skip pushing to Notion")
def portfolio(no_notion):
    """Generate the 5 portfolio demo samples."""
    from src.agent.rc_advocate import RCAdvocate
    from src.pipeline import notion_queue, logger

    out_dir = Path("portfolio")
    out_dir.mkdir(exist_ok=True)

    try:
        agent = RCAdvocate()
    except ValueError as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)

    for i, brief in enumerate(PORTFOLIO_BRIEFS, 1):
        click.echo(f"\n[{i}/5] {brief['label']}: {brief['topic'][:60]}...")

        result = agent.draft(
            topic=brief["topic"],
            channel=brief["channel"],
        )

        # Write portfolio file with full context
        content = f"""# {brief['label']}

## Input Brief
**Channel:** {brief['channel']}
**Topic:** {brief['topic']}

---

## Raw Draft Output
*Generated by RC Dev agent — {result.timestamp}*
*RAG chunks used: {result.rag_chunks_used} | Confidence: {result.confidence}*

{result.content}

---

## Human Operator Notes
*(Add editorial notes here before publishing)*

- [ ] Fact-checked against current RC docs
- [ ] Voice/tone reviewed
- [ ] Code snippets verified (if any)
- [ ] Links validated

**Operator:** Rashad Gaines
**Status:** PENDING REVIEW

---

## Final Published Version
*(Copy here after edits are applied and approved)*

"""
        out_path = out_dir / brief["filename"]
        out_path.write_text(content)

        logger.log_draft(result)

        if not no_notion:
            notion_url = notion_queue.push_draft(result)
            if notion_url:
                click.echo(f"  ✓ Notion: {notion_url}")

        click.echo(f"  ✓ Saved: {out_path}")

    click.echo(f"\n✓ Portfolio complete. {len(PORTFOLIO_BRIEFS)} samples in portfolio/")


if __name__ == "__main__":
    cli()
