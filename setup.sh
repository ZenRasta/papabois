#!/bin/bash

# Exit on error
set -e

echo "🌿 Setting up Plant Spirit Bot environment..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3 and try again."
    exit 1
fi

# Create virtual environment
echo "📦 Creating virtual environment '.venv'..."
python3 -m venv .venv

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
python3 -m pip install --upgrade pip

# Install packages
echo "📥 Installing required packages..."
pip install pyTelegramBotAPI requests python-dotenv

# Create requirements.txt
echo "📝 Creating requirements.txt..."
cat > requirements.txt << EOF
pyTelegramBotAPI
requests
python-dotenv
kindwise-api-client
EOF

# Create .env template if it doesn't exist
if [ ! -f .env ]; then
    echo "🔑 Creating .env template..."
    cat > .env << EOF
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
PLANT_API_KEY=your_plant_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
EOF
    echo "⚠️  Please update .env with your actual API keys"
fi

echo "✅ Setup complete!"
echo "To activate the environment, run: source .venv/bin/activate"