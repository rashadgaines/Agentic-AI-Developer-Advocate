#!/bin/bash
set -e

echo "=== RevenueCat AI Developer Advocate — Setup ==="

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate and install
source .venv/bin/activate
echo "Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Copy .env if it doesn't exist
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "✓ Created .env — add your API keys before running the agent."
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your ANTHROPIC_API_KEY"
echo "  2. Run: source .venv/bin/activate"
echo "  3. Run: python -m src.cli setup-notion   (get Notion setup instructions)"
echo "  4. Run: python -m src.cli ingest          (scrape RC docs + build index)"
echo "  5. Run: python -m src.cli draft --channel twitter --topic 'your topic'"
