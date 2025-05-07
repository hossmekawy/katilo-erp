import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Google Maps API key
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', 'AIzaSyAwlSE5qHU1tI8wNdwInTcSSzCSYYaa8yk')

# Other configuration settings can be added here
