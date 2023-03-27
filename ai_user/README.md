# How to use 🛠️

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

## Image scanning 🖼️

```
[p]ai_user scan_images
```

Image scanning, if turned on, will be very CPU intensive. Not recommended for multiple servers/channels.

It will require pytesseract, transformers[torch] install.

```
[p]pipinstall pytesseract transformers[torch]
```

And then the Pytesseract install will require **Google Tesseract be [installed](https://tesseract-ocr.github.io/tessdoc/Installation.html) on host machine itself or the phasecorex/red-discordbot:full image**.

First time use will take longer due to the need to download the pretrained models. (OCR and image captioning models)

### Have fun. 🎉
![repetition](https://user-images.githubusercontent.com/46238123/227853613-1a524915-ed46-45f7-a154-94e90daf0cd7.jpg)
