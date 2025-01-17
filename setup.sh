#!/bin/bash

# Script to set up a virtual environment and install dependencies

# Exit on error
set -e

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3 and try again."
    exit 1
fi

# Check if virtualenv is installed
if ! command -v virtualenv &> /dev/null; then
    echo "virtualenv is not installed. Installing virtualenv..."
    pip3 install virtualenv
fi

# Create a virtual environment
echo "Creating virtual environment '.venv'..."
python3 -m virtualenv .venv

# Activate the virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# Set up environment variables (optional)
echo "Setting up environment variables..."
if [ ! -f .env ]; then
    echo "Creating .env file..."
    touch .env
    echo "TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here" >> .env
    echo "PLANT_API_KEY=your_plant_api_key_here" >> .env
    echo "OPENROUTER_API_KEY=your_openrouter_api_key_here" >> .env
    echo "Please update the .env file with your actual API keys."
else
    echo ".env file already exists. Skipping creation."
fi

echo "Setup complete! Virtual environment is ready."
echo "To activate the virtual environment, run: source .venv/bin/activate"
