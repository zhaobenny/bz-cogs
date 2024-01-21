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

### END DEFAULTS ###

IMAGE_REQUEST_CHECK_PROMPT = "Your task is to classify messages. You are {botname}. Is the following a message asking for a picture, image, or photo that includes yourself or {botname}?  Answer with True/False."
IMAGE_REQUEST_SD_GEN_PROMPT = """ I want you to act as an Art Prompt Generator. Maintain maximum accuracy to the original user prompt. You should use Danbooru tags in the prompt.
Here are Danbooru tag examples: "holding apple, Shopping, Amusement park, sitting on a bench, cozy sweater, autumn park, colorful leaves, 4K quality".
The prompt Should be free of the following: line breaks, close-up, dots, delimiters, underscores, photographing, english articles (a, an, and the).
Convert the below message into an Art Prompt.
Keep the prompt as short as possible.
DO NOT GENERATE OR RESPOND IF THE PROMPT IS SEXUAL IN ANY WAY.
DO NOT GENERATE OR RESPOND IF THE PROMPT CONTAINS ANY NUDITY"""

IMAGE_REQUEST_SD_GEN_PROMPT = IMAGE_REQUEST_SD_GEN_PROMPT.replace("\\", "").replace("\"", "").replace("taking picture of", "").replace("capturing a photograph", "").replace("photographer", "").replace("photographing", "").replace("taking photo of", "")
# misc
MIN_MESSAGE_LENGTH = 5
MAX_MESSAGE_LENGTH = 1000  # in words

# local image captioning
IMAGE_UPLOAD_LIMIT = 2 * (1024 * 1024)  # 2 MB


# models
FUNCTION_CALLING_SUPPORTED_MODELS = [
    "gpt-4",
    "gpt-4-1106-preview",
    "gpt-4-0613",
    "gpt-3.5-turbo",
    "gpt-3.5-turbo-1106",
    "gpt-3.5-turbo-0613",
    "openai/gpt-4",
    "openai/gpt-4-1106-preview",
    "openai/gpt-4-0613",
    "openai/gpt-3.5-turbo",
    "openai/gpt-3.5-turbo-1106",
    "openai/gpt-3.5-turbo-0613"
]
VISION_SUPPORTED_MODELS = [
    "gpt-4-vision-preview",
    "openai/gpt-4-vision-preview",
    "haotian-liu/llava-13b",
    "nousresearch/nous-hermes-2-vision-7b"
]
OTHER_MODELS_LIMITS = {
    "gpt-3.5-turbo-1106": 12000,
    "gpt-4-1106-preview": 123000,
    "gpt-4-vision-preview": 123000,
    "claude-2": 98000,
    "claude-instant-v1": 98000,
    "dolphin-mixtral-8x7b": 31000,
    "mistral-tiny": 31000,
    "mistral-small": 31000,
    "mistral-medium": 31000,
    "toppy-m-7b": 31000,
    "nous-capybara-34b": 31000,
    "stripedhyena-hessian-7b": 31000,
    "stripedhyena-nous-7b": 31000,
    "mythomist-7b": 31000,
    "cinematika-7b": 31000,
    "mixtral-8x7b-instruct": 31000,
    "mixtral-8x7b": 31000,
    "gemini-pro": 31000,
    "gemini-pro-vision": 15000,
    "rwkv-5-world-3b": 9000,
    "rwkv-5-3b-ai-town": 9000,
    "noromaid-mixtral-8x7b-instruct": 7000,
    "bagel-34b": 7000,
    "pplx-7b-chat": 7000,
    "noromaid-20b": 7000,
    "palm-2-chat-bison": 7000,
    "claude-v1": 7000,
    "claude-1.2": 7000,
    "claude-instant-1.0": 7000,
    "codellama-34b-instruct": 6000,
    "synthia-70b": 6000,
    "mistral-7b-instruct": 6000,
    "mistral-7b-openorca": 6000,
    "mythalion-13b": 6000,
    "xwin-lm-70b": 6000,
    "goliath-120b": 6000,
    "weaver": 6000,
    "palm-2-codechat-bison": 6000,
    "openchat-7b": 6000,
    "remm-slerp-l2-13b": 5000
}
