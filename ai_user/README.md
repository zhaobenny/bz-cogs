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

See custom prompt settings in:
```
[p]ai_user prompt
```

Optionally, enable slash (/chat) command using:
```
[p]slash enablecog ai_user
[p]slash sync
```

See other settings using:

```
[p]ai_user
```

### Have fun. 🎉
![repetition](https://user-images.githubusercontent.com/46238123/227853613-1a524915-ed46-45f7-a154-94e90daf0cd7.jpg)

---

## Image scanning 🖼️

![image_seeing](https://github.com/zhaobenny/bz-cogs/assets/46238123/8b0019f3-8b38-4578-b511-a350e10fce2d)


See settings here:
```
[p]ai_user image
```

### AI Horde Image Scanning Mode
Utilize [AI Horde's](https://stablehorde.net/) Image Alchemy to caption images.


AI Horde is a crowdsourced distributed cluster. Please contribute back if heavily used.

Compared to local captioning mode:
#### Pros
1. No need to manually install dependencies
2. Good x86 CPU not needed
3. No load on machine, that Redbot is running on

#### Cons
1. Images will be uploaded to a **third party** (a volunteer worker machine)
2. May be a queue if there are no workers available (faster if you have an [API key](https://stablehorde.net/register) and [kudos](https://dbzer0.com/blog/the-kudos-based-economy-for-the-koboldai-horde/))
3. No OCR, only image captioning


### Local Image Scanning Mode

Local image scanning mode will be very CPU intensive. (Not recommended for busy servers/channel)
First, images will be OCR'ed for text to use. If the OCR is not of significant confidence, it will be captioned instead using [BLIP](https://huggingface.co/Salesforce/blip-image-captioning-base).

See below for instructions on installing the necessary dependencies. *(x86 only)*


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

---

### Custom OpenAI endpoint

⚠️ For advanced users! ⚠️

OpenAI-Compatible API endpoints can be used instead of the default OpenAI API. (eg. gpt4all or FastChat)

This can be set using:
```
[p]ai_user response custom_openai <ENDPOINT>
```
Third party models may have undesirable results.
