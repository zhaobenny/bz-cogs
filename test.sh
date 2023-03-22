#!/bin/bash
# Start my test bot
pyenv local 3.9.16
source ./.venv/bin/activate
redbot dev_bzbot --dev
