# OpenAI Chat

A simple, cross-platform desktop chat client for OpenAI's API.

## Features

- Clean chat interface (like ChatGPT)
- Chat history with sidebar
- Multiple model support (GPT-4o, GPT-4, GPT-3.5, o1, o3-mini)
- Works on Windows, macOS, and Linux
- Enter sends message, Shift+Enter for new line

## Quick Start

```bash
cd src
dotnet run
```

## Build

```bash
cd src
dotnet build -c Release
```

The executable will be in `src/bin/Release/net8.0/`

## Requirements

- [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0)
- OpenAI API key from [platform.openai.com](https://platform.openai.com/api-keys)

## Usage

1. Run the app
2. Enter your OpenAI API key
3. Select a model
4. Start chatting!

## Data Storage

**API Key:**
- **Windows** - Windows Credential Manager (secure, not in a file)
- **Linux** - `~/.config/OpenAICommunicator/key` with 600 permissions (owner-only)
- **Alternative** - Set `OPENAI_API_KEY` environment variable

**Chat History:** 
- `%AppData%/OpenAICommunicator/history.json` (Windows)
- `~/.config/OpenAICommunicator/history.json` (Linux)
