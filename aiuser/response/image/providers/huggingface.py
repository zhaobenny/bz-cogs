import io

from gradio_client import Client

from aiuser.response.image.providers.generator import ImageGenerator

# When Setting Endpoints from huggingface do not use any using ZERO or you will require an API key with Credits
# Get endpoints/spaces from here https://huggingface.co/spaces?category=image-generation&p=1&sdk=gradio

# These endpoints were tested and work:
# https://huggingface.co/spaces/HiDream-ai/HiDream-I1-Dev/
# https://huggingface.co/spaces/llamameta/Fake-FLUX-Pro-Unlimited/
# https://huggingface.co/spaces/neta-art/NetaLumina_T2I_Playground/


def extract_hf_space(endpoint: str) -> str:
    """Extracts the huggingface space name from a huggingface.co or .hf.space endpoint."""
    import re

    # Match huggingface.co/spaces/{org}/{space}
    m = re.match(r"https?://huggingface.co/spaces/([^/]+)/([^/?#]+)", endpoint)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    # Match huggingface.co/{org}/{space}
    m = re.match(r"https?://huggingface.co/([^/]+)/([^/?#]+)", endpoint)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    # Match {org}-{space}.hf.space
    m = re.match(r"https?://([a-z0-9\-]+)\.hf\.space", endpoint)
    if m:
        # Try to reconstruct org/space from subdomain (best effort)
        sub = m.group(1)
        # e.g. llamameta-fake-flux-pro-unlimited -> llamameta/Fake-FLUX-Pro-Unlimited
        # This is a guess: split on first dash
        parts = sub.split("-", 1)
        if len(parts) == 2:
            org, space = parts
            return f"{org}/{space.replace('-', ' ').title().replace(' ', '-')}"
        return sub
    raise ValueError(f"Cannot extract Hugging Face space from endpoint: {endpoint}")


HUGGINGFACE_API = "/generate_image"
DEFAULT_MODEL = "flux"


class HuggingFaceGenerator(ImageGenerator):
    _api_info_cache = None

    async def _get_api_info(self):
        if HuggingFaceGenerator._api_info_cache is not None:
            return HuggingFaceGenerator._api_info_cache
        # Try to fetch the API info from the Space
        import aiohttp

        # Try both .hf.space and huggingface.co/spaces URLs
        api_url = None
        if self.sd_endpoint:
            if ".hf.space" in self.sd_endpoint:
                api_url = (
                    self.sd_endpoint.rstrip("/") + "/gradio_api/info?serialize=False"
                )
            elif self.sd_endpoint.startswith("https://huggingface.co/spaces/"):
                # Convert to .hf.space
                parts = self.sd_endpoint.rstrip("/").split("/")
                if len(parts) >= 6:
                    subdomain = (
                        f"{parts[4]}-{parts[5]}".replace("_", "-")
                        .replace(" ", "-")
                        .lower()
                    )
                    api_url = (
                        f"https://{subdomain}.hf.space/gradio_api/info?serialize=False"
                    )
        if not api_url:
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=10) as resp:
                    if resp.status == 200:
                        info = await resp.json()
                        HuggingFaceGenerator._api_info_cache = info
                        return info
        except Exception:
            pass
        return None

    def __init__(self, ctx, config, sd_endpoint=None):
        self.ctx = ctx
        self.config = config
        self.bot = ctx.bot
        self.sd_endpoint = sd_endpoint
        # Logging removed
        if sd_endpoint:
            try:
                self.hf_space = extract_hf_space(sd_endpoint)
                pass
            except Exception as e:
                pass
                self.hf_space = None
        else:
            pass
            self.hf_space = None

    async def _get_api_key(self, provider: str):
        # Optionally get Hugging Face token if needed for private spaces
        return (await self.bot.get_shared_api_tokens("huggingface")).get("api_key")

    async def generate_image(
        self,
        caption,
        model=DEFAULT_MODEL,
        steps=None,
        cfg_scale=None,
        height=None,
        width=None,
        negative_prompt=None,
    ):
        """Generate image using Hugging Face gradio_client."""
        api_key = await self._get_api_key("huggingface")
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = await self._prepare_payload(caption)
        api_info = await self._get_api_info()
        # Determine which API endpoint to use
        api_name = HUGGINGFACE_API
        if not (
            api_info
            and "named_endpoints" in api_info
            and api_name in api_info["named_endpoints"]
        ):
            # Fallback: use the first available endpoint
            if (
                api_info
                and "named_endpoints" in api_info
                and api_info["named_endpoints"]
            ):
                api_name = next(iter(api_info["named_endpoints"].keys()))
        predict_kwargs = {"api_name": api_name}
        # Dynamically map payload and function args to the actual parameter names required by the endpoint
        param_names = []
        if (
            api_info
            and "named_endpoints" in api_info
            and api_name in api_info["named_endpoints"]
        ):
            params = api_info["named_endpoints"][api_name].get("parameters", [])
            # Some Spaces use 'parameter_name', some use 'name'
            param_names = [
                p.get("parameter_name") or p.get("name")
                for p in params
                if p.get("parameter_name") or p.get("name")
            ]

        # Fill from payload if present
        if isinstance(payload, dict):
            for k in param_names:
                if k in payload:
                    predict_kwargs[k] = payload[k]
        # Handle prompt/prompt_text mapping, only send the one accepted by the endpoint
        prompt_value = None
        if isinstance(payload, dict):
            if "prompt" in payload:
                prompt_value = payload["prompt"]
            elif "prompt_text" in payload:
                prompt_value = payload["prompt_text"]
        if not prompt_value:
            prompt_value = caption

        # Handle model fallback if choices are present in API info
        model_choices = None
        if (
            api_info
            and "named_endpoints" in api_info
            and HUGGINGFACE_API in api_info["named_endpoints"]
        ):
            params = api_info["named_endpoints"][HUGGINGFACE_API].get("parameters", [])
            for p in params:
                pname = p.get("parameter_name") or p.get("name")
                if pname == "model" and "choices" in p:
                    model_choices = p["choices"]
                    break

        # If model is not valid, fallback to first allowed model
        model_to_use = model
        if model_choices:
            if model not in model_choices:
                model_to_use = model_choices[0] if model_choices else model

        arg_map = {
            "model": model_to_use,
            "steps": steps,
            "cfg_scale": cfg_scale,
            "height": height,
            "width": width,
            "negative_prompt": negative_prompt,
        }
        for k in param_names:
            if k in arg_map and arg_map[k] is not None and k not in predict_kwargs:
                predict_kwargs[k] = arg_map[k]

        # Always force model to be the valid fallback value if 'model' is a parameter
        if "model" in param_names:
            predict_kwargs["model"] = model_to_use

        # Only send prompt or prompt_text if accepted by the endpoint
        if "prompt" in param_names:
            predict_kwargs["prompt"] = prompt_value
            predict_kwargs.pop("prompt_text", None)
        elif "prompt_text" in param_names:
            predict_kwargs["prompt_text"] = prompt_value
            predict_kwargs.pop("prompt", None)

        # If no param_names, fallback to old behavior for prompt/model
        if not param_names:
            predict_kwargs["prompt"] = prompt_value
            predict_kwargs["model"] = model

        try:
            if not self.hf_space:
                raise Exception(
                    "No Hugging Face space set or could not extract from endpoint."
                )
            client = Client(self.hf_space, hf_token=api_key if api_key else None)
            import base64
            import aiohttp

            try:
                result = await self._run_in_executor(client.predict, **predict_kwargs)
            except ValueError as ve:
                # If error is about api_name, try again without api_name
                if "api_name" in str(ve):
                    predict_kwargs_no_api = dict(predict_kwargs)
                    predict_kwargs_no_api.pop("api_name", None)
                    result = await self._run_in_executor(
                        client.predict, **predict_kwargs_no_api
                    )
                else:
                    raise

            # gradio_client may return a dict, str, or tuple (file path/url, ...)
            if isinstance(result, dict):
                if result.get("url"):
                    if result["url"].startswith("data:image"):
                        # base64 encoded image
                        b64data = result["url"].split(",", 1)[-1]
                        image = io.BytesIO(base64.b64decode(b64data))
                    else:
                        # url to image, fetch it
                        async with aiohttp.ClientSession() as session:
                            async with session.get(result["url"]) as resp:
                                image = io.BytesIO(await resp.read())
                    return image
                elif result.get("path"):
                    with open(result["path"], "rb") as f:
                        return io.BytesIO(f.read())
                else:
                    raise Exception(f"No image returned from Hugging Face: {result}")
            elif isinstance(result, str):
                # result is a string, could be a file path or a URL
                if result.startswith("data:image"):
                    b64data = result.split(",", 1)[-1]
                    return io.BytesIO(base64.b64decode(b64data))
                elif result.startswith("http://") or result.startswith("https://"):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(result) as resp:
                            return io.BytesIO(await resp.read())
                else:
                    # Assume local file path
                    with open(result, "rb") as f:
                        return io.BytesIO(f.read())
            elif isinstance(result, tuple):
                # Use the first element as the image (file path or URL), ignore the rest
                image_result = result[0]
                if isinstance(image_result, str):
                    if image_result.startswith("data:image"):
                        b64data = image_result.split(",", 1)[-1]
                        return io.BytesIO(base64.b64decode(b64data))
                    elif image_result.startswith("http://") or image_result.startswith(
                        "https://"
                    ):
                        async with aiohttp.ClientSession() as session:
                            async with session.get(image_result) as resp:
                                return io.BytesIO(await resp.read())
                    else:
                        # Assume local file path
                        with open(image_result, "rb") as f:
                            return io.BytesIO(f.read())
                else:
                    raise Exception(
                        f"Unexpected tuple result from Hugging Face: {result}"
                    )
            else:
                raise Exception(
                    f"Unexpected result type from Hugging Face: {type(result)} {result}"
                )
        except Exception as e:
            raise

    async def _run_in_executor(self, func, *args, **kwargs):
        import asyncio

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
