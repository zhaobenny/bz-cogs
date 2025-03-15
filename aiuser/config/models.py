FUNCTION_CALLING_SUPPORTED_MODELS = [
    "o3-mini",
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
    "openai/o3-mini",
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
    "anthropic/claude-3.5-sonnet:beta",
    "qwen/qwen-2.5-72b-instruct",
    "mistralai/mistral-nemo",
    "mistralai/mistral-7b-instruct",
    "mistralai/mistral-large",
]
VISION_SUPPORTED_MODELS = [
    "o3-mini",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4-vision-preview",
    "openai/o3-mini",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "openai/gpt-4-turbo",
    "openai/gpt-4-vision-preview",
    "google/gemini-flash-1.5",
    "google/gemini-pro-1.5",
    "google/gemini-flash-1.5-8b",
    "x-ai/grok-vision-beta",
    "x-ai/grok-2-vision-1212",
    "amazon/nova-lite-v1",
    "amazon/nova-pro-v1",
    "anthropic/claude-3-haiku",
    "anthropic/claude-3-sonnet",
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3-opus",
    "anthropic/claude-3-haiku:beta",
    "anthropic/claude-3-sonnet:beta",
    "anthropic/claude-3-opus:beta",
    "anthropic/claude-3.5-sonnet:beta"
    "qwen/qwen-2-vl-72b-instruct",
    "qwen/qwen-2.5-72b-instruct",
    "qwen/qvq-72b-preview",
    "mistralai/pixtral-12b",
    "mistralai/pixtral-12b:free",
    "mistralai/pixtral-large-2411",
    "meta-llama/llama-3.2-90b-vision-instruct",
    "meta-llama/llama-3.2-11b-vision-instruct"
]
UNSUPPORTED_LOGIT_BIAS_MODELS = [
    "openai/o3-mini",
    "o3-mini",
    "o3-mini-2025-01-31"
]
OTHER_MODELS_LIMITS = {
    "gemini-flash-1.5": 2797000,
    "gemini-pro-1.5": 3998000,
    "o1": 198000,
    "o3-mini": 198000,
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
    "o1-preview": 123000,
    "o1-mini": 123000,
    "deepseek-r1": 123000,
    "deepseek-chat": 123000,
    "x-ai/grok-vision-beta": 7800,
    "grok-2-vision-1212": 31000,
    "command-r-plus": 123000,
    "phi-3-medium-128k-instruct": 123000,
    "mistral-nemo": 123000,
    "deepseek-coder": 123000,
    "qwen-2-vl-72b-instruct": 123000,
    "hermes-3-llama-3.1-405b": 123000,
    "claude-2": 98000,
    "claude-instant-v1": 98000,
    "command-r": 98000,
    "mixtral-8x22b": 60000,
    "mixtral-8x22b-instruct": 60000,
    "wizardlm-2-8x22b": 60000,
    "zephyr-orpo-141b-a35b": 60000,
    "wizardlm-2-7b": 31000,
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
    "qvq-72b-preview": 123000,
    "llama-3.1-70b-instruct": 31000,
    "mistral-tiny": 28000,
    "mistral-small": 28000,
    "mistral-medium": 28000,
    "mistral-large": 28000,
    "soliloquy-l3": 21000,
    "llama-3-lumimaid-8b": 21000,
    "sonar-small-chat": 18000,
    "sonar-medium-chat": 18000,
    "magnum-v4-72b": 15000,
    "gemini-pro-vision": 15000,
    "gemini-2.0-flash-exp": 1000000,
    "gemini-2.0-flash-thinking-exp": 36000,
    "learnlm-1.5-pro-experimental": 38000,
    "gemini-exp-1206": 2000000,
    "gemini-exp-1121": 38000,
    "gemini-flash-1.5-8b": 960000,
    "nova-lite-v1": 280000,
    "nova-pro-v1": 280000,
    "pixtral-12b": 3800,
    "pixtral-large-2411": 120000,
    "gpt-3.5-turbo-1106": 12000,
    "sonar-small-online": 8000,
    "sonar-medium-online": 8000,
    "gemma-2-9b-it": 7000,
    "openchat-7b": 7000,
    "gemma-7b-it": 7000,
    "llama-3-8b-instruct": 7000,
    "llama-3.2-90b-vision-instruct": 120000,
    "llama-3.2-11b-vision-instruct": 120000
}
