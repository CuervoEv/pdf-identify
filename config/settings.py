import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TEMP_DIR = os.path.join(os.path.dirname(__file__), "..", "temp")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Configuración de fuente para inserción de texto
DEFAULT_FONT_NAME = "Arial"
DEFAULT_FONT_SIZE = 12
MIN_FONT_SIZE = 6
MAX_FONT_SIZE = 36

# Configuración de coordenadas
COORDINATE_SCALE = 1000  # Gemini retorna coordenadas normalizadas 0-1000
