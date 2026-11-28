import re

RANDOM_MESSAGE_TASK_RETRY_SECONDS = 33 * 60

GROK_PRIMARY_TRIGGERS = ["grok", "gork"]
GROK_SECONDARY_TRIGGERS = ["true", "explain", "confirm"]
GROK_MAX_WORDS = 25

FALLBACK_TOKENIZER = "cl100k_base"

# regex patterns
URL_PATTERN = re.compile(r"(https?://\S+)")
YOUTUBE_URL_PATTERN = re.compile(
    r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?(.+)"
)
YOUTUBE_VIDEO_ID_PATTERN = re.compile(
    r"(?:youtube(?:-nocookie)?\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/|v\/|t\/\S*?\/?)([a-zA-Z0-9_-]{11})"
)
SINGULAR_MENTION_PATTERN = re.compile(r"^<@!?&?(\d+)>$")
CHANNEL_MENTION_OR_ID_PATTERN = re.compile(r"(?:<#(\d{15,25})>|(\d{15,25}))")
REGEX_RUN_TIMEOUT = 5


OPENROUTER_URL = "https://openrouter.ai/api/"
OPENROUTER_API_V1_URL = f"{OPENROUTER_URL}v1/"
OPENROUTER_DECISIONS_URL = f"{OPENROUTER_URL}alpha/decisions"
OPENAI_DECISIONS_URL = "https://api.openai.com/v1/decisions"
TYPESAFE_DECISIONS_URL = "https://api.typesafe.ai/v1/systemone"

DEFAULT_OPENAI_DECISION_MODEL = "gpt-6-luna"
DEFAULT_OPENROUTER_DECISION_MODEL = "typesafe/jev-1.14"
DEFAULT_TYPESAFE_DECISION_MODEL = "jev-latest"
DECISION_CONTEXT_MAX_MESSAGES = 10
DECISION_REQUEST_TIMEOUT = 15

EMBEDDING_MODEL = "Snowflake/snowflake-arctic-embed-s"
EMBEDDING_CACHE_DIR_NAME = "fastembed_cache"
EMBEDDING_DB_NAME = "embeddings.sqlite"
COMPACTION_DB_NAME = "compaction.sqlite"

GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image-preview"
