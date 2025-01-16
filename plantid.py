import os
import argparse
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

def identify_plant(image_path: str, api_key: str) -> None:
    """Identify a plant from an image file using Kindwise API."""
    try:
        # Verify file exists
        if not Path(image_path).is_file():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # Initialize API
        logger.info("Initializing Kindwise API...")
        api = PlantApi(api_key=api_key)

        # Send identification request
        logger.info(f"Processing image: {image_path}")
        identification = api.identify(
            image_path,
            details=['common_names', 'taxonomy', 'description'],
            language=['en'],
            similar_images=True,
            date_time=datetime.now(),
            asynchronous=True
        )
        
        logger.info(f"Identification token: {identification.access_token}")
        
        # Wait for results
        logger.info("Waiting for results...")
        completed_identification = api.get_identification(identification.access_token)
        
        if not completed_identification.completed:
            logger.error("Identification did not complete")
            return
            
        # Process results
        if not hasattr(completed_identification, 'result') or \
           not hasattr(completed_identification.result, 'classification'):
            logger.error("No classification results available")
            return

        suggestions = completed_identification.result.classification.suggestions
        if not suggestions:
            logger.info("No plant matches found")
            return

        # Print top matches
        print("\n🌿 Plant Identification Results:")
        print("=" * 50)
        
        for idx, suggestion in enumerate(suggestions[:3], 1):
            print(f"\n{idx}. {suggestion.name}")
            print(f"   Confidence: {suggestion.probability:.1%}")
            
            # Get additional details from knowledge base
            try:
                search_result = api.search(suggestion.name, language='en', limit=1)
                if search_result.entities:
                    details = api.get_kb_detail(
                        search_result.entities[0].access_token,
                        details=['common_names', 'description'],
                        language='en'
                    )
                    
                    if 'common_names' in details:
                        print(f"   Common names: {', '.join(details['common_names'])}")
                    if 'description' in details:
                        print(f"   Description: {details['description'][:200]}...")
            
                # Get healing properties for top match only
                if idx == 1:
                    print("\n   Healing Properties:")
                    healing_props = api.ask_question(
                        completed_identification.access_token,
                        "What are the traditional medicinal and healing properties of this plant?",
                        model="gpt-3.5-turbo.demo"
                    )
                    if healing_props and hasattr(healing_props, 'messages'):
                        print(f"   {healing_props.messages[-1].content[:200]}...")
                        
            except Exception as e:
                logger.error(f"Error getting additional details: {str(e)}")
                
        print("\n" + "=" * 50)

    except Exception as e:
        logger.error(f"Error during plant identification: {str(e)}")
        raise

def main():
    parser = argparse.ArgumentParser(description='Identify plants from images using Kindwise API')
    parser.add_argument('image_path', help='Path to the plant image file')
    parser.add_argument('--api-key', help='Kindwise API key (optional if PLANT_API_KEY environment variable is set)')
    args = parser.parse_args()

    # Get API key from args or environment
    api_key = args.api_key or os.getenv('PLANT_API_KEY')
    if not api_key:
        parser.error("API key must be provided either as an argument or through PLANT_API_KEY environment variable")

    identify_plant(args.image_path, api_key)

if __name__ == "__main__":
    main()