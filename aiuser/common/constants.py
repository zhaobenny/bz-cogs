OPENAI_MODEL_TOKEN_LIMIT = {
    "gpt-4-0613": 7000,
    "gpt-4-32k-0613": 31000,
    "gpt-3.5-turbo-16k-0613": 31000,
    "gpt-4": 7000,
    "gpt-4-0314": 7000,
    "gpt-3.5-turbo": 3000,
    "gpt-3.5-turbo-0301": 3000,
    "gpt-3.5-turbo-16k": 15000,
    "gpt-3.5-turbo-0613": 3000
}
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
    "fitness and health,",
    "politics",
    "science",
    "cooking",
]
DEFAULT_REPLY_PERCENT = 0.5
MIN_MESSAGE_LENGTH = 5
MAX_MESSAGE_LENGTH = 1000  # in words
IMAGE_RESOLUTION = 1024
IMAGE_TIMEOUT = 60
LOCAL_MODE = "local"
AI_HORDE_MODE = "ai-horde"
SCAN_IMAGE_MODES = [LOCAL_MODE, AI_HORDE_MODE]
