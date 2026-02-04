# OpenAI API Communicator

A local GPT chat client with a Qt GUI and optional CLI mode.

## Features
- API key field with secure save option (keyring)
- Model categories with refresh from the API
- Model stats panel with pricing metadata
- System prompt presets and editor
- Wrapper prompt layer (toggle in UI)
- Pricing reload button reads static `model-catalog.json`
- Conversation history stored locally in JSON (multiple chats, per-conversation model)
- Chat-style Qt GUI plus CLI mode

## Install
```bash
python -m pip install -r requirements.txt
```

## Run (GUI)
```bash
python main.py
```

## Run (CLI)
```bash
python main.py --cli
```

## API Key
- Enter it in the GUI and click Save Key (stored in system keyring when available), or
- Set `OPENAI_API_KEY` in your environment.

## Local storage
- Config: `~/.openai-api-communicator/config.json`
- Conversations: `~/.openai-api-communicator/history.json`

## Catalog and prompts
- Model catalog: `model-catalog.json` (categories, release order, pricing metadata)
- Prompt presets: `system-prompts.json`
- Wrapper prompt: `wrapper-prompt.json`
- Models are sorted oldest-to-newest using API timestamps when available; catalog release order is the fallback.

## Pricing updates
- Use the **Reload Pricing** button in the sidebar to re-read the local `model-catalog.json`.
- If you change prices, edit `model-catalog.json` directly.

Notes:
- Pricing is read from `model-catalog.json` and may need updates.
- Wrapper prompt runs before the selected system prompt; disable it in the UI or CLI `/wrapper off`.
- The API key is stored in the system keyring when available; otherwise it falls back to plain text config storage.
- Model categories are inferred from model IDs returned by the API.
