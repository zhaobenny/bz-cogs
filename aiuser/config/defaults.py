import json
from datetime import datetime

from aiuser.types.enums import ScanImageMode

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
DEFAULT_IMAGE_REQUEST_SD_GEN_PROMPT = """
I want you to act as a Stable Diffusion Art Prompt Generator. The formula for a prompt is made of parts, the parts are indicated by brackets. The [Subject] is the person place or thing the image is focused on. [Emotions] is the emotional look the subject or scene might have. [Verb] is What the subject is doing, such as standing, jumping, working and other varied that match the subject. [Adjectives] like beautiful, rendered, realistic, tiny, colorful and other varied that match the subject. The [Environment] in which the subject is in, [Lighting] of the scene like moody, ambient, sunny, foggy and others that match the Environment and compliment the subject. [Photography type] like Polaroid, long exposure, monochrome, GoPro, fisheye, bokeh and others. And [Quality] like High definition, 4K, 8K, 64K UHD, SDR and other. The subject and environment should match and have the most emphasis.
It is ok to omit one of the other formula parts. Each formula part should be less then four words.

Here is a sample output: "Beautiful woman, contemplative and reflective, sitting on a bench, cozy sweater, autumn park with colorful leaves, soft overcast light, muted color photography style, 4K quality."

Convert the below message to a Stable Diffusion Art Prompt.  The prompt should have no second person references, no line breaks, no delimiters, and be kept as concise as possible while still conveying a full scene.
"""
DEFAULT_REMOVE_PATTERNS = [
    r"<\s*think\s*>[\s\S]*?<\s*/\s*think\s*>",  # for thinking LLMs
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
DEFAULT_IMAGE_REQUEST_TRIGGER_WORDS = [
    "image",
    "images",
    "picture",
    "pictures",
    "photo",
    "photos",
    "photograph",
    "photographs",
]
DEFAULT_IMAGE_REQUEST_TRIGGER_SECOND_PERSON_WORDS = ["yourself", "you"]
DEFAULT_REPLY_PERCENT = 0.5
DEFAULT_MIN_MESSAGE_LENGTH = 2
DEFAULT_IMAGE_UPLOAD_LIMIT = 10 * (1024 * 1024)  # 10 MB
DEFAULT_LLM_MODEL = "gpt-4o-mini"

DEFAULT_GLOBAL = {
    "custom_openai_endpoint": None,
    "openai_endpoint_request_timeout": 60,
    "optout": [],
    "optin": [],
    "ratelimit_reset": datetime(1990, 1, 1, 0, 1).strftime("%Y-%m-%d %H:%M:%S"),
    "max_random_prompt_length": 200,
    "max_prompt_length": 200,
    "custom_text_prompt": None,
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
    "scan_images_mode": ScanImageMode.AI_HORDE.value,
    "scan_images_model": DEFAULT_LLM_MODEL,
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
    "image_requests": False,
    "image_requests_endpoint": "dall-e-2",
    "image_requests_parameters": None,
    "image_requests_sd_gen_prompt": DEFAULT_IMAGE_REQUEST_SD_GEN_PROMPT,
    "image_requests_preprompt": "",
    "image_requests_subject": "woman",
    "image_requests_reduced_llm_calls": False,
    "image_requests_trigger_words": DEFAULT_IMAGE_REQUEST_TRIGGER_WORDS,
    "image_requests_second_person_trigger_words": DEFAULT_IMAGE_REQUEST_TRIGGER_SECOND_PERSON_WORDS,
    "function_calling": False,
    "function_calling_functions": [],
    "function_calling_default_location": [49.24966, -123.11934],
    "conversation_reply_percent": 0,
    "conversation_reply_time": 20,
    "custom_model_tokens_limit": None,
}

DEFAULT_CHANNEL = {"custom_text_prompt": None, "reply_percent": None}
DEFAULT_ROLE = {"custom_text_prompt": None, "reply_percent": None}

DEFAULT_MEMBER = {"custom_text_prompt": None, "reply_percent": None}

DEFAULT_DM_PROMPT = "You are {botname}. You are in a private Discord DM conversation. \
Fulfill your persona and speak as such and don't speak in third person. \
You are forbidden from saying you're an AI or a bot."
