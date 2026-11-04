#!/usr/bin/env bash
# Copies the Default ("합니다체") post, the tone conversion input, to the working folder.
set -e
cp "$(dirname "$0")/article-default.md" ./article-default.md
