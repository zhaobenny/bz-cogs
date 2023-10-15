# How to use 🛠️

The bot will generate responses in whitelisted channels. Bot owners can add a channel to a server's whitelist using:
```
[p]aiuser add <CHANNEL>
```

Bot owners can change the percentage of eligible messages (per server) to reply to:
```
[p]aiuser percent <PERCENT>
```

Users will also have to opt-in (bot-wide) into having their messages used:
```
[p]aiuser optin
```

Admins can modify prompt settings in:
```
[p]aiuser prompt
```

Optionally, enable slash (/chat) command using:
```
[p]slash enablecog aiuser
[p]slash sync
```

Some additional settings are restricted to bot owner only.
See other settings using:
```
[p]aiuser
[p]aiuserowner
```

### Have fun. 🎉
![repetition](https://user-images.githubusercontent.com/46238123/227853613-1a524915-ed46-45f7-a154-94e90daf0cd7.jpg)

---

## Image scanning 🖼️

![image_seeing](https://github.com/zhaobenny/bz-cogs/assets/46238123/8b0019f3-8b38-4578-b511-a350e10fce2d)


Bot owners can see settings here:
```
[p]aiuser image
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
1. Privacy issues, images will be uploaded to a **third party** (a random volunteer worker machine)
2. May be a queue if there are no workers available (faster if you have an [API key](https://stablehorde.net/register) and [kudos](https://dbzer0.com/blog/the-kudos-based-economy-for-the-koboldai-horde/))
3. No OCR, only image captioning


### Local Image Scanning Mode

Local image scanning mode will be **very CPU intensive**. *(Not recommended for busy servers/channel)*

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

## Random Messages 🎲

Dead chat? No problem. Let the bot send random messages!

Every 33 minutes, a RNG roll will determine if a random message will be sent using a list of topics as a prompt.

Whitelisted channels must have a hour pass without a message sent in it for a random message to be sent, and the last sent message must be sent by a user.

Bot owners see settings here:
```
[p]aiuser triggers random
```

Admins manage topics here:
```
[p]aiuser prompt topics
```
---

## Prompt/Topics Variables  📝

Prompts and topics can include certain variables by including one of the following strings:

- `{botname}` - the bot's current nickname or username
- `{authorname}` - the author of the message the bot is activated on
- `{servername}` - the server name
- `{channelname}` - the channel name
- `{currentdate}` - the current date eg. 2023/08/31
- `{currentweekday}` - the current weekday eg. Monday
- `{currenttime}` - the current 24-hour time eg. 21:59

Remove list regex patterns only support `{authorname}` (will use authors of last 10 messages) and `{botname}` strings.

---
### Custom OpenAI endpoint

⚠️ For advanced users! ⚠️

OpenAI-Compatible API endpoints can be used instead of the default OpenAI API. (eg. gpt4all or text-generation-webui, for a local and more private alternative to OpenAI)

Bot owners can set this globally using:
```
[p]aiuser endpoint <ENDPOINT>
```

Models will also need **changing** per server.


Third party models may have undesirable results! (I tested this [one](https://huggingface.co/mindrage/Manticore-13B-Chat-Pyg-Guanaco-GGML) and the results are decent-ish)

Bot owners may also want to set custom parameters (per server). See:
```
[p]aiuser response parameters
```
