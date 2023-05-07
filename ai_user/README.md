# How to use 🛠️

The bot will only reply in whitelisted channels.
Please add a channel to a server's whitelist using:

```
[p]ai_user add <#CHANNEL_MENTION>
```

Change the percentage of eligible messages to reply to (defaults to 50% per server):

```
[p]ai_user percent <PERCENT>
```

See other settings using:

```
[p]ai_user
```

See custom prompt settings in:
```
[p]ai_user prompt
```

This option (enabled by default) filters out responses that contains any of the following words: "language model", "openai", "sorry"
Most responses with these words are pretty generic and bias the model away from the prompt.
```
[p]ai_user filter_responses
```

Enable slash (/chat) command using:
```
[p]slash enablecog ai_user
[p]slash sync
```

### Have fun. 🎉
![repetition](https://user-images.githubusercontent.com/46238123/227853613-1a524915-ed46-45f7-a154-94e90daf0cd7.jpg)

---

## Image scanning 🖼️

See settings here:
```
[p]ai_user image
```

### AI Horde Image Scanning Mode
Utilize [AI Horde's](https://stablehorde.net/) Image Alchemy to caption images.


AI Horde is a crowdsourced distributed cluster. Please contribute back if heavily used.

#### Pros vs Local mode
1. No need to manually install dependencies
2. No need for a powerful x86 CPU

#### Limitations vs Local mode
1. Images will be uploaded to a third party (a volunteer worker machine)
2. May be a queue if there are no workers available (faster if you have an [API key](https://stablehorde.net/#:~:text=0%20alchemy%20forms.-,Usage,-First%20Register%20an) and kudos)
3. No OCR, only image captioning
4. No confidence levels, so can not ignore bad captions


### Local Image Scanning Mode

Local image scanning mode will be very CPU intensive. Not recommended for busy servers/channels. First, images will be OCR'ed for text to use. If the OCR is not of significant confidence, it will be captioned instead, and the caption will be used if it is of significant confidence.

See below for instructions on installing the necessary dependencies. (ARM not supported)


#### 1. Install Python Dependencies

```
source ~/redenv/bin/activate # or however you activate your virtual environment in your OS
pip install -U pytesseract transformers[torch]
```

OR (less recommended) run this command in Discord

```
[p]pipinstall pytesseract transformers[torch]
```

#### 2. Install Tessaract OCR

See [here](https://tesseract-ocr.github.io/tessdoc/Installation.html) for instructions on installing TessaractOCR, or alternatively just use the phasecorex/red-discordbot:full image.



First time scanning an image will take longer due to the need to download the pretrained models. (OCR and image captioning models)

(For Docker installs, I also recommend binding  `/config/.cache/huggingface/hub` to a persistent volume to avoid redownloading the models every time the container is restarted)

---
