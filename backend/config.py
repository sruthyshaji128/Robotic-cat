
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", 9000))
    DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
    WEBCAM_INDEX = int(os.getenv("WEBCAM_INDEX", 0))
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", 0.5))

config = Config()
