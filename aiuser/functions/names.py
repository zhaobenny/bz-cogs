"""Tool (function-calling) name constants.

This module must stay import-free so that any layer can reference a tool by
name without importing the tool's implementation (which may pull in heavy
dependencies or higher layers).
"""

DO_NOT_RESPOND = "do_not_respond"
ADD_REACTION = "add_reaction"
GET_DISCORD_INFO = "get_discord_info"
IMAGE_REQUEST = "image_request"
VOICE_REQUEST = "voice_request"
OPEN_URL = "open_url"
SEARCH_WEB = "search_web"
GET_WEATHER = "get_weather"
IS_DAYTIME = "is_daytime"
ASK_WOLFRAM_ALPHA = "ask_wolfram_alpha"
RUN_PYTHON_CODE = "run_python_code"
SAVE_MEMORY = "save_memory"
READ_MEMORY = "read_memory"
