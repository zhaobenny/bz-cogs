# How to use 🛠️

The bot will only reply in whitelisted channels. Do not use mention, just the channel name to whitelist.
Please add a channel to a server's whitelist using:

```
[p]ai_user add <CHANNEL_NAME>
```

Change the percentage of eligible messages to reply to (defaults to 50% per server):

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

This option (enabled by default) filters out responses that contains any words in "language model", "openai", "sorry", "apologize".
Most responses with these words are pretty generic and bias the model away from the prompt.
```
[p]ai_user filter_responses
```

## Image scanning 🖼️

```
[p]ai_user scan_images
```

Image scanning, if turned on, will be very CPU intensive. Not recommended for multiple servers/channels.
See below for instructions on installing the necessary dependencies. (ARM not supported)


### 1. Install Python Dependencies

```
source ~/redenv/bin/activate # or however you activate your virtual environment in your OS
pip install -U pytesseract transformers[torch]
```

OR (less recommended) run this command in Discord

```
[p]pipinstall pytesseract transformers[torch]
```

### 2. Install Tessaract OCR

See [here](https://tesseract-ocr.github.io/tessdoc/Installation.html) for instructions on installing TessaractOCR, or alternatively just use the phasecorex/red-discordbot:full image.



First time scanning an image will take longer due to the need to download the pretrained models. (OCR and image captioning models)

---

### Have fun. 🎉
![repetition](https://user-images.githubusercontent.com/46238123/227853613-1a524915-ed46-45f7-a154-94e90daf0cd7.jpg)
