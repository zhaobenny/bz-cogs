# How to use

The bot will only reply in whitelisted channels. Do not use mention, just the channel name to whitelist.
Please add a channel to whitelist using:

```
[p]ai_user add <CHANNEL_NAME>
```

Change the percentage of eligible messages to reply to (default 50):

```
[p]ai_user percent <PERCENT>
```

See other settings using:

```
[p]ai_user
```

Custom prompts can be set per server using the commands in:
```
[p]ai_user prompt
```

## Image scanning

```
[p]ai_user scan_images
```

Image scanning, if turned on, will be very CPU intensive. Not recommended for multiple servers/channels.

It will require pytesseract, transformers[torch] install.

Pytesseract install requires **Google Tesseract be installed on host machine itself or the phasecorex/red-discordbot:full image**.

First time use will take longer due to the need to download the pretrained models. (OCR and image captioning models)
