echo " Starting FastAPI Backend..."
echo "   API Docs: http://localhost:8000/api/docs"
echo ""

cd "$(dirname "$0")"

# Check if virtual env exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
