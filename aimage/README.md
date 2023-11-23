# How to use 🛠️

This will requires your own [Automatic1111](https://github.com/AUTOMATIC1111/stable-diffusion-webui) Stable Diffusion endpoint to be set up first.

Currently only supports basic txt2img functionality and some configuration options.

Recommended to enable slash (/imagine) command using:
```
[p]slash enablecog aimage
[p]slash sync
```

Settings are located here:
```
[p]aimage
[p]aimageowner
```

NSFW filter is disabled by default, you can enable it by installing/enabling [this script](https://github.com/IOMisaka/sdapi-scripts) in A1111 then using:
```
[p]aimage nsfw
```