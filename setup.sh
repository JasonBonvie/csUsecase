#!/usr/bin/env sh
# Heroku Streamlit setup - configures headless mode and port

mkdir -p ~/.streamlit/

echo "[server]
headless = true
enableCORS = false
port = $PORT
" > ~/.streamlit/config.toml
