import sys
from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env file

from src.bot import main as bot_main

if __name__ == "__main__":
    print("Démarrage du TikTok Trend Predictor...")
    try:
        bot_main()
    except KeyboardInterrupt:
        print("Arrêt du bot.")
