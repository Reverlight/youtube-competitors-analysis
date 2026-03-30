# youtube-competitor-analysis
 
An [OpenClaw](https://openclaw.ai) skill that analyzes YouTube competitor channels and generates data-driven content ideas.
 
## What it does
 
- Fetches your channel's videos from the past 30 days via the YouTube Data API v3
- Fetches competitor channels' videos from the past 7 days
- Saves all data locally as CSV files
- Analyzes trending topics, title patterns, and performance gaps
- Suggests specific video ideas based on what's actually working for competitors right now
 
## Requirements
 
- UV installed https://docs.astral.sh/uv/#highlights
- A Google OAuth 2.0 Client ID ([get one here](https://console.cloud.google.com/apis/credentials)) with YouTube Data API v3 enabled
