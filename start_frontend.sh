echo " Starting React Frontend..."
echo "   App: http://localhost:3000"
echo ""

cd "$(dirname "$0")/frontend"

# Install if node_modules missing
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

npm run dev
