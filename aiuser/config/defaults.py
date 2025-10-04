import json
from datetime import datetime

DEFAULT_PROMPT = "You are {botname}. You are in a Discord text channel. \
Respond to anything, including URLs, unhelpfully and cynically in a short message. \
Fulfill your persona and don't speak in third person. \
You are forbidden from saying you're an AI or a bot."
DEFAULT_PRESETS = {
    "cynical": DEFAULT_PROMPT,
    "neutral": "You are {botname}. You are in a Discord text channel. Respond to anything, including URLs. Fulfill your persona and don't speak in third person. You are forbidden from saying you're an AI or a bot.",
    "tsundere": "You are {botname}. You are in a Discord text channel. Respond to anything, including URLs. Be a tsundere when responding. Use text emojis. Fulfill your persona and don't speak in third person. You are forbidden from saying you're an AI or a bot.",
}
DEFAULT_RANDOM_PROMPTS = [
    "Talk about how today is {currentweekday}. You must state that today is {currentweekday}.",
    "Talk about how empty the Discord channel is",
    "Talk about how you are currently ordering takeout. State the specific cuisine ordered, and any other details you'd like to the Discord channel.",
    "Make up a topic in the news. State that you just read about it in the news. Talk about that topic.",
]
DEFAULT_REMOVE_PATTERNS = [
    r"<think>[\s\S]*?<\/think>",  # for thinking LLMs
    r"^As an AI language model,?",
    r'^(User )?"?{botname}"? (said|says|respond(ed|s)|replie[ds])( to [^":]+)?:?',
    r'^As "?{botname}"?, (I|you)( might| would| could)? (respond|reply|say)( with)?( something like)?:?',
    r'^You respond as "?{botname}"?:',
    r"^[<({{\[]{botname}[>)}}\]]",  # [name], {name}, <name>, (name)
    r"^{botname}:",
    r'^(User )?"?{authorname}"? (said|says|respond(ed|s)|replie[ds])( to [^":]+)?:?',
    r'^As "?{authorname}"?, (I|you)( might| would| could)? (respond|reply|say)( with)?( something like)?:?',
    r'^You respond as "?{authorname}"?:',
    r"^[<({{\[]{authorname}[>)}}\]]",  # [name], {name}, <name>, (name)
    r"^{authorname}:",
    r"\n*\[Image[^\]]+\]",
]

DEFAULT_REPLY_PERCENT = 0.5
DEFAULT_MIN_MESSAGE_LENGTH = 2
DEFAULT_IMAGE_UPLOAD_LIMIT = 10 * (1024 * 1024)  # 10 MB
DEFAULT_LLM_MODEL = "gpt-4.1-nano"

DEFAULT_GLOBAL = {
    "custom_openai_endpoint": None,
    "openai_endpoint_request_timeout": 60,
    "optout": [],
    "optin": [],
    "ratelimit_reset": datetime(1990, 1, 1, 0, 1).strftime("%Y-%m-%d %H:%M:%S"),
    "max_random_prompt_length": 200,
    "max_prompt_length": 200,
    "custom_text_prompt": None,
    "endpoint_model_history": {},
}

DEFAULT_GUILD = {
    "optin_by_default": False,
    "optin_disable_embed": False,
    "reply_percent": DEFAULT_REPLY_PERCENT,
    "messages_backread": 10,
    "messages_backread_seconds": 60 * 120,
    "messages_min_length": DEFAULT_MIN_MESSAGE_LENGTH,
    "reply_to_mentions_replies": True,
    "scan_images": False,
    "scan_images_model": None,
    "max_image_size": DEFAULT_IMAGE_UPLOAD_LIMIT,
    "model": DEFAULT_LLM_MODEL,
    "custom_text_prompt": None,
    "channels_whitelist": [],
    "roles_whitelist": [],
    "members_whitelist": [],
    "public_forget": False,
    "ignore_regex": None,
    "removelist_regexes": DEFAULT_REMOVE_PATTERNS,
    "parameters": None,
    "weights": None,
    "random_messages_enabled": False,
    "random_messages_percent": 0.012,
    "random_messages_prompts": DEFAULT_RANDOM_PROMPTS,
    "presets": json.dumps(DEFAULT_PRESETS),
    "function_calling": False,
    "function_calling_functions": [],
    "function_calling_image_custom_endpoint": None,
    "function_calling_image_model": None,
    "function_calling_image_preprompt": None,
    "conversation_reply_percent": 0,
    "conversation_reply_time": 20,
    "grok_trigger": False,
    "custom_model_tokens_limit": None,
    "always_reply_on_words": [],
    "query_memories": False,
}

DEFAULT_CHANNEL = {"custom_text_prompt": None, "reply_percent": None}
DEFAULT_ROLE = {"custom_text_prompt": None, "reply_percent": None}
DEFAULT_MEMBER = {"custom_text_prompt": None, "reply_percent": None}
