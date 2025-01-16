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

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Please set the TELEGRAM_BOT_TOKEN env var")
if not PLANT_API_KEY:
    raise ValueError("Please set the PLANT_API_KEY env var")

# Initialize bot and API
state_storage = StateMemoryStorage()
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, state_storage=state_storage)
bot.add_custom_filter(StateFilter(bot))
api = PlantApi(api_key=PLANT_API_KEY)

class UserStates(StatesGroup):
    waiting_for_photo = State()

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
            asynchronous=False  # Wait for results
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
            
            # Get additional details
            try:
                search_result = api.search(suggestion.name, language='en', limit=1)
                if search_result.entities:
                    details = api.get_kb_detail(
                        search_result.entities[0].access_token,
                        details=['common_names', 'description'],
                        language='en'
                    )
                    plant_info["details"] = details
                    
                # Get healing properties for top match only
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

        # Format response
        response = "🌿 *Plant Identification Results*\n\n"
        for idx, plant in enumerate(identification_result["results"], 1):
            response += f"{idx}. *{plant['name']}*\n"
            response += f"   Confidence: {plant['confidence']:.1%}\n"
            
            if plant['details'].get('common_names'):
                response += f"   Common names: {', '.join(plant['details']['common_names'])}\n"
            
            if plant['details'].get('description'):
                response += f"   Description: {plant['details']['description'][:200]}...\n"
            
            if idx == 1 and 'healing_properties' in plant:
                response += f"\n   Healing Properties:\n   {plant['healing_properties'][:200]}...\n"
            
            response += "\n"

        # Send results
        bot.edit_message_text(
            response,
            message.chat.id,
            processing_msg.message_id,
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
    