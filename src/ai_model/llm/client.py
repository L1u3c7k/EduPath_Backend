

from openai import OpenAI
from src.config import settings

API_KEY = settings.OPENROUTER_API_KEY
BASE_URL = settings.OPENROUTER_API_BASE


if not API_KEY:
    raise ValueError(
        "OPENROUTER_API_KEY is missing"
    )

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)


def is_client_available():

    return True