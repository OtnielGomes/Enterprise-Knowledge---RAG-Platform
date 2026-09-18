import os

os.environ["OPENAI_API_KEY"] = ""

from ask.settings import get_settings

get_settings.cache_clear()
