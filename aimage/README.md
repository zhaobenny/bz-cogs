# How to use 🛠️

This will requires your own [Automatic1111](https://github.com/AUTOMATIC1111/stable-diffusion-webui) Stable Diffusion endpoint to be set up first.

Supports txt2img and img2img functionality.

**Highly recommended** to enable slash (/imagine) command using:
```
[p]slash enablecog aimage
[p]slash sync
```

All settings are located here:
```
[p]aimage
[p]aimageowner
```

NSFW filter is disabled by default, you can enable it by installing/enabling [this script](https://github.com/IOMisaka/sdapi-scripts) in A1111 then using:
```
[p]aimage nsfw
```

The cog will fall back to using AI Horde (a crowdsourced volunteer service) if no endpoints are available by default. (Some parameters are not supported by AI Horde, and are ignored silently)

# Credits 👏

Coauthored with: [halostrawberry](https://github.com/hollowstrawberry)