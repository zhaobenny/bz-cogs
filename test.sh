#!/bin/bash
# Start my test bot
source ./.venv/bin/activate
export AIUSER_DEBUG_GUILD="${AIUSER_DEBUG_GUILD:-744802856074346556}"
redbot dev_bzbot --dev --debug # --rpc

# source ./.dashboard-venv/bin/activate
# reddash
