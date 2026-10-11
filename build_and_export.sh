#!/usr/bin/env bash
set -e

echo "=== Building The Plague Docker Image ==="
docker build -t the-plague-bot:latest .

echo "=== Exporting Image to the-plague-bot.tar ==="
docker save -o the-plague-bot.tar the-plague-bot:latest

echo "=== SUCCESS! Image saved to: the-plague-bot.tar ==="
