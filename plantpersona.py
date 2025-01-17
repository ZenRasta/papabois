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

# Define states
class UserStates(StatesGroup):
    waiting_for_photo = State()

# Initialize bot and APIs
state_storage = StateMemoryStorage()
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, state_storage=state_storage)
bot.add_custom_filter(StateFilter(bot))
api = PlantApi(api_key=PLANT_API_KEY)

def get_openrouter_response(prompt: str) -> str:
    """Helper function to call OpenRouter API directly"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://github.com/",
        "X-Title": "Plant Spirit Bot",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {
                "role": "system",
                "content": "You are a mystical plant spirit, sharing ancient wisdom about your nature and properties."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            logger.error(f"OpenRouter Error: Status {response.status_code} - {response.text}")
            return "The spirits are quiet at the moment... 🌿"
    except Exception as e:
        logger.error(f"OpenRouter API error: {str(e)}")
        return "Nature's wisdom is temporarily veiled... 🍃"

def get_plant_persona(plant_info: dict) -> str:
    """Get a personalized response from the plant using OpenRouter."""
    try:
        prompt = f"""You are {plant_info['name']}, speaking as a mystical plant entity.
        
Scientific Details:
- Name: {plant_info['name']}
- Common Names: {', '.join(plant_info.get('common_names', []))}
- Description: {plant_info.get('description', 'A mysterious plant of ancient wisdom')}
- Healing Properties: {plant_info.get('healing_properties', 'Powers yet to be fully understood')}

Share your story in a mystical, wise voice, covering:
1. Your origins and native lands
2. Your healing powers and gifts to humanity
3. What brings you joy in the natural world
4. Ancient wisdom or warnings you wish to share

Remember, speak as the plant itself, sharing deep wisdom while being engaging and unique."""

        return get_openrouter_response(prompt)
    except Exception as e:
        logger.error(f"Error in get_plant_persona: {str(e)}")
        return "The ancient wisdom eludes me at this moment... 🌿"

def get_healing_properties(plant_name: str) -> str:
    """Get healing properties using OpenRouter."""
    try:
        prompt = f"What are the traditional medicinal and healing properties of {plant_name}? Include both benefits and any potential risks or warnings."
        return get_openrouter_response(prompt)
    except Exception as e:
        logger.error(f"Error getting healing properties: {str(e)}")
        return "Properties yet to be discovered..."

def identify_plant_from_path(image_path: str) -> dict:
    """Identify a plant from an image file using Kindwise API."""
    try:
        if not Path(image_path).is_file():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # Send identification request
        logger.info(f"Processing image: {image_path}")
        identification = api.identify(
            image_path,
            details=['taxonomy', 'common_names', 'description'],
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
                "confidence": suggestion.probability
            }
            
            # Get common names and description directly from suggestion object
            if hasattr(suggestion, 'details'):
                plant_info.update(suggestion.details)

            # Get healing properties using OpenRouter for top match
            if suggestion == suggestions[0]:
                plant_info['healing_properties'] = get_healing_properties(suggestion.name)

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
    main()
    