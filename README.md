# Consensia Agent

AI-powered Telegram monitoring for real-time channel/group tracking, event detection (hacks, bounties, large transfers), and on-chain verification via Bitquery + Web3.

---

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Setup](#setup)
- [Environment Variables](#environment-variables)
- [Run](#run)
- [API Endpoints](#api-endpoints)

---

## Overview

The project uses a small asynchronous pipeline:

1. Telegram interceptor (`pyrogram`)
Reads messages from monitored channels/groups through a userbot account.

2. AI pipeline (`transformers`, `peft`)
Cleans incoming text, filters noise, and decides whether a message should be escalated.

3. Blockchain verifier (Python + Bitquery API)
Checks suspicious events against on-chain transfer data.

4. On-chain enrichment (`web3.py`)
Resolves ENS names and checks contract verification via Sourcify.

5. Web interface and API (`fastapi`)
Serves UI from `dist`, exposes control endpoints, and streams live logs over WebSocket.

6. Notifier bot
Sends verified alerts to a private Telegram chat.

---

## Requirements

- OS: Linux or Windows (WSL2 recommended)
- Hardware: NVIDIA GPU with CUDA support (required for Qwen 1.5B and 3B)
- Python: 3.10+
- Node.js: required only if you build the frontend yourself
- Hugging Face CLI: `hf`

---

## Setup

Clone the repository and create a Python environment:

```bash
git clone <your-repo-url>
cd consensia
python -m venv venv
source venv/bin/activate
# Windows:
# venv\Scripts\activate
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Authenticate Hugging Face CLI:

```bash
hf auth login
```

The project loads adapters directly from Hugging Face:

- `itsSHAS/consensia-tagger-1.5b-lora`
- `itsSHAS/consensia-analyzer_3B_lora_final`

If you change model repos, update `TAGGER_LORA` and `ANALYZER_LORA` in `main.py`.

---

## Environment Variables

Create a `.env` file in the project root:

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

Keep `dist` in the same repository as `main.py`:

- Backend serves static frontend directly from `dist`
- If `dist` is missing, API + Telegram bots still work
- Web UI will not be served without `dist`

---

## Run

Start the agent:

```bash
python main.py
```

Or run with Uvicorn:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

On first launch, Pyrogram asks for Telegram login (phone + verification code) and creates `consensia_userbot.session` automatically.

---

## API Endpoints

Once running, the backend exposes:

- UI: `http://localhost:8000/`
- WebSocket logs: `ws://localhost:8000/ws/logs`
- Toggle agent: `POST /api/toggle`
- Status: `GET /api/status`
- Update monitored channels: `POST /api/settings`
- Get available chats: `GET /api/sources`
