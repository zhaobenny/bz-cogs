import re

RANDOM_MESSAGE_TASK_RETRY_SECONDS = 33 * 60

GROK_PRIMARY_TRIGGERS = ["grok", "gork"]
GROK_SECONDARY_TRIGGERS = ["true", "explain", "confirm"]
GROK_MAX_WORDS = 25

FALLBACK_TOKENIZER = "cl100k_base"

# regex patterns
URL_PATTERN = re.compile(r"(https?://\S+)")
YOUTUBE_URL_PATTERN = re.compile(r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?(.+)")
YOUTUBE_VIDEO_ID_PATTERN = re.compile(
    r"(?:youtube(?:-nocookie)?\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/|v\/|t\/\S*?\/?)([a-zA-Z0-9_-]{11})")
SINGULAR_MENTION_PATTERN = re.compile(r"^<@!?&?(\d+)>$")
REGEX_RUN_TIMEOUT = 5


OPENROUTER_URL = "https://openrouter.ai/api/"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DB_NAME = "lancedb"

GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image-preview"
