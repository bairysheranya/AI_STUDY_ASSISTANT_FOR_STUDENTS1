#!/usr/bin/env bash
set -e
GREEN='\033[0;32m'; AMBER='\033[0;33m'; NC='\033[0m'
echo ""
echo "🎓 AI Study Assistant — Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
command -v python3 &>/dev/null || { echo "Python 3 not found"; exit 1; }
echo -e "${GREEN}✓ Python $(python3 --version 2>&1 | cut -d' ' -f2)${NC}"
[ ! -d "venv" ] && python3 -m venv venv && echo -e "${GREEN}✓ venv created${NC}"
source venv/bin/activate
pip install --upgrade pip -q && pip install -r requirements.txt -q
echo -e "${GREEN}✓ Dependencies installed${NC}"
[ ! -f ".env" ] && cp .env.example .env && echo -e "${AMBER}⚠  Created .env — add your OPENAI_API_KEY${NC}"
mkdir -p uploads
python3 -c "from app import init_db; init_db(); print('✓ Database ready')"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Done! Run: source venv/bin/activate && python app.py${NC}"
echo "   Then open: http://localhost:5000"
