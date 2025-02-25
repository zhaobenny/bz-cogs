from datetime import datetime
import json

from aiuser.config.constants import DEFAULT_IMAGE_REQUEST_SD_GEN_PROMPT, DEFAULT_IMAGE_REQUEST_TRIGGER_SECOND_PERSON_WORDS, DEFAULT_IMAGE_REQUEST_TRIGGER_WORDS, DEFAULT_IMAGE_UPLOAD_LIMIT, DEFAULT_MIN_MESSAGE_LENGTH, DEFAULT_PRESETS, DEFAULT_RANDOM_PROMPTS, DEFAULT_REMOVE_PATTERNS, DEFAULT_REPLY_PERCENT
from aiuser.types.enums import ScanImageMode


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
    "scan_images_model": "gpt-4o",
    "max_image_size": DEFAULT_IMAGE_UPLOAD_LIMIT,
    "model": "gpt-3.5-turbo",
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

DEFAULT_CHANNEL = {
    "custom_text_prompt": None,
    "reply_percent": None
}
DEFAULT_ROLE = {
    "custom_text_prompt": None,
    "reply_percent": None
}

DEFAULT_MEMBER = {
    "custom_text_prompt": None,
    "reply_percent": None
}
