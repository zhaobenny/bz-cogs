# How to use 🛠️

This will requires your own [Automatic1111](https://github.com/AUTOMATIC1111/stable-diffusion-webui)-compatible Stable Diffusion endpoint to be set up first.

For A1111 API setup, see [here](https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/API). (Some necessary flags may be  `--api`, or `--listen`)

Supports txt2img and img2img functionality.

**Highly recommended** to enable slash (`/imagine`) command using:
```
[p]slash enablecog aimage
[p]slash sync
```

The non-slash command is `[p]imagine`, and is very limited in functionality.

# Settings ⚙️

All settings are located here:
```
[p]aimage # per server
[p]aimageowner # bot wide
```

NSFW filter is disabled by default, you can enable it by installing/enabling [this script](https://github.com/IOMisaka/sdapi-scripts) in A1111 then using:
```
[p]aimage nsfw
```

## AI Horde 🤖

The cog will fall back to using AI Horde (a crowdsourced volunteer service) if no endpoints are available by default. (Some parameters are not supported by AI Horde, and are ignored silently)

This can be toggled using `[p]aimageowner aihorde`.

# Credits 👏

Coauthored with: [halostrawberry](https://github.com/hollowstrawberry)
