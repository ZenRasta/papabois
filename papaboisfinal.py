import sys
import subprocess
import pkg_resources

def check_and_install_dependencies():
    """Check and install required dependencies."""
    required_packages = {
        'pyTelegramBotAPI': 'telebot',
        'kindwise-api-client': 'kindwise',
        'requests': 'requests'
    }
    
    missing_packages = []
    
    # Check which packages are missing
    for package, import_name in required_packages.items():
        try:
            pkg_resources.get_distribution(package)
        except pkg_resources.DistributionNotFound:
            missing_packages.append(package)
    
    if missing_packages:
        print("\nSome required packages are missing:")
        for package in missing_packages:
            print(f"  - {package}")
            
        response = input("\nWould you like to install them now? (y/n): ").lower()
        if response == 'y':
            print("\nInstalling dependencies...")
            for package in missing_packages:
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                    print(f"Successfully installed {package}")
                except subprocess.CalledProcessError as e:
                    print(f"Error installing {package}: {str(e)}")
                    sys.exit(1)
            print("\nAll dependencies installed successfully!")
            return True
        else:
            print("\nCannot continue without required packages. Exiting...")
            sys.exit(1)
    
    return True

# Original code starts here
import os
import telebot
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
from telebot.custom_filters import StateFilter
from datetime import datetime
from kindwise import PlantApi, PlantIdentification
import logging
import sys
from pathlib import Path
import requests
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PLANT_API_KEY = os.getenv("PLANT_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Validate environment variables
for var_name, var_value in {
    "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
    "PLANT_API_KEY": PLANT_API_KEY,
    "OPENROUTER_API_KEY": OPENROUTER_API_KEY
}.items():
    if not var_value:
        raise ValueError(f"Please set the {var_name} env var")

# Initialize bot and API
state_storage = StateMemoryStorage()
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, state_storage=state_storage)
bot.add_custom_filter(StateFilter(bot))
api = PlantApi(api_key=PLANT_API_KEY)

# Define states
class UserStates(StatesGroup):
    waiting_for_photo = State()

def get_plant_persona(plant_info: dict) -> str:
    """Get a personalized response from the plant using OpenRouter/Grok."""
    try:
        prompt = f"""You are {plant_info['name']}, a mystical plant entity. 
Based on this information about yourself:
- Scientific name: {plant_info['name']}
- Common names: {', '.join(plant_info['details'].get('common_names', []))}
- Description: {plant_info['details'].get('description', 'Unknown')}
- Healing properties: {plant_info.get('healing_properties', 'Unknown')}

Introduce yourself and tell us about who you are, where you're from, your benefits, and what makes you happy. 
Speak in a mystical, wise, and enchanting voice, as if you're an ancient being sharing your wisdom.
Keep the response concise but magical."""

        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "http://localhost",
                "X-Title": "Plant Spirit Bot",
            },
            data=json.dumps({
                "model": "x-ai/grok-2-1212",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            })
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            logger.error(f"OpenRouter API error: {response.text}")
            return "I seem to be in deep meditation at the moment... 🌿"

    except Exception as e:
        logger.error(f"Error getting plant persona: {str(e)}")
        return "I am currently communing with nature... Try again later 🌱"

def identify_plant_from_path(image_path: str) -> dict:
    """Identify a plant from an image file using Kindwise API."""
    try:
        if not Path(image_path).is_file():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # Send identification request
        logger.info(f"Processing image: {image_path}")
        identification = api.identify(
            image_path,
            details=['common_names', 'taxonomy', 'description'],
            language=['en'],
            similar_images=True,
            date_time=datetime.now(),
            asynchronous=False
        )

        # Check results
        if not hasattr(identification, 'result') or \
           not hasattr(identification.result, 'classification'):
            return {"error": "No classification results available"}

        suggestions = identification.result.classification.suggestions
        if not suggestions:
            return {"error": "No plant matches found"}

        # Process results
        results = []
        for suggestion in suggestions[:3]:
            plant_info = {
                "name": suggestion.name,
                "confidence": suggestion.probability,
                "details": {}
            }
            
            try:
                search_result = api.search(suggestion.name, language='en', limit=1)
                if search_result.entities:
                    details = api.get_kb_detail(
                        search_result.entities[0].access_token,
                        details=['common_names', 'description'],
                        language='en'
                    )
                    plant_info["details"] = details
                    
                if suggestion == suggestions[0]:
                    healing_props = api.ask_question(
                        identification.access_token,
                        "What are the traditional medicinal and healing properties of this plant?",
                        model="gpt-3.5-turbo.demo"
                    )
                    if healing_props and hasattr(healing_props, 'messages'):
                        plant_info["healing_properties"] = healing_props.messages[-1].content
            except Exception as e:
                logger.error(f"Error getting additional details: {str(e)}")

            results.append(plant_info)

        return {"success": True, "results": results}

    except Exception as e:
        logger.error(f"Error during plant identification: {str(e)}")
        return {"error": str(e)}

@bot.message_handler(commands=['start'])
def cmd_start(message):
    """Handle /start command"""
    logger.info(f"Received /start from user {message.from_user.id}")
    bot.reply_to(
        message,
        "🌿 Welcome! This bot identifies plants from photos using Kindwise.\n"
        "Type /whois_plant to begin."
    )

@bot.message_handler(commands=['whois_plant'])
def cmd_whois_plant(message):
    """Handle /whois_plant command"""
    logger.info(f"Received /whois_plant from user {message.from_user.id}")
    bot.set_state(message.from_user.id, UserStates.waiting_for_photo, message.chat.id)
    bot.reply_to(message, "📸 Please send me a photo of the plant you want to identify.")

@bot.message_handler(content_types=['photo'], state=UserStates.waiting_for_photo)
def handle_photo(message):
    """Handle received photos"""
    logger.info(f"Received photo from user {message.from_user.id}")
    try:
        # Send processing message
        processing_msg = bot.reply_to(message, "🔍 Processing your plant photo... Please wait...")

        # Download photo
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Save photo temporarily
        photo_path = f"temp_plant_{message.from_user.id}.jpg"
        with open(photo_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        # Identify plant
        identification_result = identify_plant_from_path(photo_path)

        if "error" in identification_result:
            bot.edit_message_text(
                f"❌ {identification_result['error']}",
                message.chat.id,
                processing_msg.message_id
            )
            return

        # Format initial response with identification results
        response = "🌿 *Plant Identification Results*\n\n"
        for idx, plant in enumerate(identification_result["results"], 1):
            response += f"{idx}. *{plant['name']}*\n"
            response += f"   Confidence: {plant['confidence']:.1%}\n\n"

        # Send initial results
        bot.edit_message_text(
            response,
            message.chat.id,
            processing_msg.message_id,
            parse_mode="Markdown"
        )

        # Get plant persona for the highest confidence match
        top_plant = identification_result["results"][0]
        bot.reply_to(message, "🌟 Let me channel the spirit of this plant...")
        
        plant_message = get_plant_persona(top_plant)
        
        # Send the plant's personal message
        bot.reply_to(
            message,
            f"✨ *A message from your plant:*\n\n{plant_message}",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        bot.reply_to(message, f"❌ An error occurred: {str(e)}")

    finally:
        # Cleanup
        if 'photo_path' in locals() and os.path.exists(photo_path):
            os.remove(photo_path)
        bot.delete_state(message.from_user.id, message.chat.id)

@bot.message_handler(state=UserStates.waiting_for_photo, content_types=['text', 'document', 'audio', 'video'])
def handle_invalid_input(message):
    """Handle invalid input when expecting photo"""
    bot.reply_to(message, "Please send a photo 📸 of the plant you want to identify.")

def main():
    logger.info("Starting Plant Identification Bot...")
    bot.infinity_polling()

if __name__ == "__main__":
    # Check dependencies first
    check_and_install_dependencies()
    # Start the bot
    main()