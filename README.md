Consensia Agent

Consensia is an AI-powered Telegram monitoring system for tracking channels and groups in real time, detecting events such as hacks, bounties, or large transfers, and verifying suspicious activity with Bitquery and Web3 integrations.

## Overview

The project is organized around a small asynchronous pipeline:

- Telegram interceptor (`pyrogram`): reads messages from monitored channels and groups through a userbot account.
- AI pipeline (`transformers`, `peft`): cleans incoming text, filters noise, and decides whether a message should be escalated.
- Blockchain verifier (Python + Bitquery API): checks suspicious events against on-chain transfer data.
- On-chain enrichment (`web3.py`): resolves ENS names and checks contract verification via Sourcify.
- Web interface and API (`fastapi`): serves the UI from `dist`, exposes control endpoints, and streams live logs over WebSocket.
- Notifier bot: sends verified alerts to a private Telegram chat.

## Requirements

OS: Linux or Windows (WSL2 recommended).

Hardware: NVIDIA GPU with CUDA support (required for running Qwen 1.5B and 3B models).

Python: Version 3.10 or higher.

Node.js: For building the React frontend.

Hugging Face CLI: The `hf` tool for model management.

## Setup

1. Clone the repository and create a Python environment:

```bash
git clone <your-repo-url>
cd consensia
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Make sure your Hugging Face adapters are available:

```bash
hf auth login
```

The project loads these adapter repositories directly from Hugging Face:

- `itsSHAS/consensia-tagger-1.5b-lora`
- `itsSHAS/consensia-analyzer_3B_lora_final`

If you change the model repos later, update `TAGGER_LORA` and `ANALYZER_LORA` in `main.py`.

4. Create a `.env` file in the project root and add your credentials:

```env
# Telegram Userbot Credentials (get from my.telegram.org)
USERBOT_API_ID=12345678
USERBOT_API_HASH=your_api_hash_here

# Telegram Bot Credentials (get from @BotFather)
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
ALERT_CHAT_ID=-1001234567890

# Bitquery API (for blockchain search)
BITQUERY_API_KEY=your_bitquery_api_key_here
```

5. Keep the `dist` folder in the same repository as `main.py`:

The backend serves the static frontend directly from `dist`, so no local frontend build step is required.

If `dist` is missing, the API and Telegram bots still work, but the web UI is not served.

## Run

Start the agent with:

```bash
python main.py
```

You can also run it directly with Uvicorn:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

On first launch, Pyrogram will ask you to log in to your Telegram userbot account. Enter your phone number and the verification code from Telegram. A session file named `consensia_userbot.session` will be created automatically.

## API

Once the app is running, the backend exposes:

- UI: `http://localhost:8000/`
- WebSocket logs: `ws://localhost:8000/ws/logs`
- Toggle agent: `POST /api/toggle`
- Status: `GET /api/status`
- Update monitored channels: `POST /api/settings`
- Get available chats: `GET /api/sources`
