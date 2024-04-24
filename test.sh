#!/bin/bash
# Start my test bot
pyenv local 3.8.1
source ./.venv/bin/activate
redbot dev_bzbot --dev --debug --rpc

# source ./.dashboard-venv/bin/activate
# reddash
