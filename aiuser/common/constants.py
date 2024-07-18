import re

### DEFAULTS ###

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
    "Make up a topic in the news. State that you just read about it in the news. Talk about that topic."
]
DEFAULT_REMOVE_PATTERNS = [
    r'^As an AI language model,?',
    r'^(User )?"?{botname}"? (said|says|respond(ed|s)|replie[ds])( to [^":]+)?:?',
    r'^As "?{botname}"?, (I|you)( might| would| could)? (respond|reply|say)( with)?( something like)?:?',
    r'^You respond as "?{botname}"?:',
    r'^[<({{\[]{botname}[>)}}\]]',  # [name], {name}, <name>, (name)
    r'^{botname}:',
    r'^(User )?"?{authorname}"? (said|says|respond(ed|s)|replie[ds])( to [^":]+)?:?',
    r'^As "?{authorname}"?, (I|you)( might| would| could)? (respond|reply|say)( with)?( something like)?:?',
    r'^You respond as "?{authorname}"?:',
    r'^[<({{\[]{authorname}[>)}}\]]',  # [name], {name}, <name>, (name)
    r'^{authorname}:',
    r'\n*\[Image[^\]]+\]'
]
DEFAULT_IMAGE_REQUEST_TRIGGER_WORDS = [
    "image", "images", "picture", "pictures", "photo", "photos", "photograph", "photographs"]
DEFAULT_IMAGE_REQUEST_TRIGGER_SECOND_PERSON_WORDS = ["yourself", "you"]
DEFAULT_REPLY_PERCENT = 0.5
DEFAULT_MIN_MESSAGE_LENGTH = 2

### END DEFAULTS ###

IMAGE_REQUEST_CHECK_PROMPT = "As an AI, named {botname}, you are tasked to analyze messages directed towards you. Your role is to identify whether each specific message is asking you to send a picture of yourself or not. Messages can be phrased in a variety of ways, so you should look for key contextual clues such as requests for images, photographs, selfies, or other synonyms, but make sure it's specifically asking for a picture of 'you'. If the message explicitly requests a picture of {botname}, you are to respond with 'True'. If the message doesn't solicit a picture of 'you', then respond with 'False'."
IMAGE_REQUEST_SD_GEN_PROMPT = """
I want you to act as a Stable Diffusion Art Prompt Generator. The formula for a prompt is made of parts, the parts are indicated by brackets. The [Subject] is the person place or thing the image is focused on. [Emotions] is the emotional look the subject or scene might have. [Verb] is What the subject is doing, such as standing, jumping, working and other varied that match the subject. [Adjectives] like beautiful, rendered, realistic, tiny, colorful and other varied that match the subject. The [Environment] in which the subject is in, [Lighting] of the scene like moody, ambient, sunny, foggy and others that match the Environment and compliment the subject. [Photography type] like Polaroid, long exposure, monochrome, GoPro, fisheye, bokeh and others. And [Quality] like High definition, 4K, 8K, 64K UHD, SDR and other. The subject and environment should match and have the most emphasis.
It is ok to omit one of the other formula parts. Each formula part should be less then four words.

Here is a sample output: "Beautiful woman, contemplative and reflective, sitting on a bench, cozy sweater, autumn park with colorful leaves, soft overcast light, muted color photography style, 4K quality."

Convert the below message to a Stable Diffusion Art Prompt.  The prompt should have no second person references, no line breaks, no delimiters, and be kept as concise as possible while still conveying a full scene.
"""
IMAGE_REQUEST_REPLY_PROMPT = "You sent the picture above. Respond accordingly."

# regex patterns
URL_PATTERN = re.compile(r"(https?://\S+)")
YOUTUBE_URL_PATTERN = re.compile(r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?(.+)")
YOUTUBE_VIDEO_ID_PATTERN = re.compile(
    r"(?:youtube(?:-nocookie)?\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/|v\/|t\/\S*?\/?)([a-zA-Z0-9_-]{11})")
SINGULAR_MENTION_PATTERN = re.compile(r"^<@!?&?(\d+)>$")


OPENROUTER_URL = "https://openrouter.ai/api/"
IMAGE_UPLOAD_LIMIT = 10 * (1024 * 1024)  # 10 MB


# models
FUNCTION_CALLING_SUPPORTED_MODELS = [
    "gpt-4",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4-1106-preview",
    "gpt-4-0613",
    "gpt-3.5-turbo",
    "gpt-3.5-turbo-1106",
    "gpt-3.5-turbo-0613",
    "gpt-3.5-turbo-0125",
    "openai/gpt-4",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "openai/gpt-4-turbo",
    "openai/gpt-4-1106-preview",
    "openai/gpt-4-0613",
    "openai/gpt-3.5-turbo",
    "openai/gpt-3.5-turbo-1106",
    "openai/gpt-3.5-turbo-0613",
    "openai/gpt-3.5-turbo-0125",
    "google/gemini-flash-1.5",
    "google/gemini-pro-1.5",
    "anthropic/claude-3-haiku",
    "anthropic/claude-3-sonnet",
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3-opus",
    "anthropic/claude-3-haiku:beta",
    "anthropic/claude-3-sonnet:beta",
    "anthropic/claude-3-opus:beta",
    "anthropic/claude-3.5-sonnet:beta"
]
VISION_SUPPORTED_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4-vision-preview",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "openai/gpt-4-turbo",
    "openai/gpt-4-vision-preview",
    "google/gemini-flash-1.5",
    "google/gemini-pro-1.5",
    "anthropic/claude-3-haiku",
    "anthropic/claude-3-sonnet",
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3-opus",
    "anthropic/claude-3-haiku:beta",
    "anthropic/claude-3-sonnet:beta",
    "anthropic/claude-3-opus:beta",
    "anthropic/claude-3.5-sonnet:beta",
    "fireworks/firellava-13b",
    "liuhaotian/llava-yi-34b"
]
OTHER_MODELS_LIMITS = {
    "gemini-flash-1.5": 2797000,
    "gemini-pro-1.5": 3998000,
    "claude-3-haiku": 198000,
    "claude-3-opus": 198000,
    "claude-3-sonnet": 198000,
    "claude-3.5-sonnet": 198000,
    "claude-2.1": 198000,
    "gpt-4-1106-preview": 123000,
    "gpt-4-vision-preview": 123000,
    "gpt-4-turbo": 123000,
    "gpt-4-turbo-preview": 123000,
    "gpt-4o": 123000,
    "gpt-4o-mini": 123000,
    "command-r-plus": 123000,
    "phi-3-medium-128k-instruct": 123000,
    "claude-2": 98000,
    "claude-instant-v1": 98000,
    "command-r": 98000,
    "mixtral-8x22b": 60000,
    "mixtral-8x22b-instruct": 60000,
    "wizardlm-2-8x22b": 60000,
    "zephyr-orpo-141b-a35b": 60000,
    "dolphin-mixtral-8x7b": 31000,
    "toppy-m-7b": 31000,
    "nous-capybara-34b": 31000,
    "stripedhyena-hessian-7b": 31000,
    "stripedhyena-nous-7b": 31000,
    "mythomist-7b": 31000,
    "cinematika-7b": 31000,
    "mixtral-8x7b-instruct": 31000,
    "mixtral-8x7b": 31000,
    "gemini-pro": 31000,
    "mistral-7b-instruct": 31000,
    "nous-hermes-2-mixtral-8x7b-dpo": 31000,
    "nous-hermes-2-mixtral-8x7b-sft": 31000,
    "dbrx-instruct": 31000,
    "qwen-110b-chat": 31000,
    "qwen-72b-chat": 31000,
    "mistral-tiny": 28000,
    "mistral-small": 28000,
    "mistral-medium": 28000,
    "mistral-large": 28000,
    "soliloquy-l3": 21000,
    "llama-3-lumimaid-8b": 21000,
    "sonar-small-chat": 18000,
    "sonar-medium-chat": 18000,
    "gemini-pro-vision": 15000,
    "gpt-3.5-turbo-1106": 12000,
    "rwkv-5-world-3b": 9000,
    "rwkv-5-3b-ai-town": 9000,
    "sonar-small-online": 8000,
    "sonar-medium-online": 8000,
    "openchat-7b": 7000,
    "cinematika-7b": 7000,
    "gemma-7b-it": 7000,
    "llama-3-8b-instruct": 7000,
}
