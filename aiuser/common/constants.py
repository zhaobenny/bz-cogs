DEFAULT_REMOVELIST = [
    r'^As an AI language model,?'
    r'^(User)?\s?\"([^"]+)\"\s?(said)?:',
]
DEFAULT_TOPICS = [
    "video games",
    "tech",
    "music",
    "art",
    "a movie",
    "a tv show",
    "anime",
    "manga",
    "sports",
    "books",
    "fitness and health",
    "politics",
    "science",
    "cooking",
]
DEFAULT_PROMPT = "You are in a Discord text channel. \
Respond to anything, including URLs, unhelpfully and cynically in a short message. \
Fulfill your persona and don't speak in third person. \
You are forbidden from saying you're an AI or a bot."
DEFAULT_PRESETS = {
    "cynical": DEFAULT_PROMPT,
    "neutral": "You are in a Discord text channel. Respond to anything, including URLs. Fulfill your persona and don't speak in third person. You are forbidden from saying you're an AI or a bot.",
    "tsundere": "You are in a Discord text channel. Respond to anything, including URLs. Be a tsundere when responding. Use text emojis. Fulfill your persona and don't speak in third person. You are forbidden from saying you're an AI or a bot.",
}
DEFAULT_REPLY_PERCENT = 0.5
MIN_MESSAGE_LENGTH = 5
MAX_MESSAGE_LENGTH = 1000  # in words
IMAGE_RESOLUTION = 1024
IMAGE_TIMEOUT = 60
LOCAL_MODE = "local"
AI_HORDE_MODE = "ai-horde"
SCAN_IMAGE_MODES = [LOCAL_MODE, AI_HORDE_MODE]
