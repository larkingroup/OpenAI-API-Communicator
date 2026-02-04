import argparse
import time

from app.openai_client import send_chat
from app.prompts import DEFAULT_SYSTEM_PROMPT, load_prompt_library, load_wrapper_prompt
from app.storage import (
    load_config,
    load_conversations,
    new_conversation,
    resolve_api_key,
    save_config,
    save_conversations,
    store_api_key,
)
from app.ui import run_gui


def run_cli(config, conversations, active_id):
    prompt_library = load_prompt_library()
    prompt_map = {prompt["id"]: prompt for prompt in prompt_library["prompts"]}
    default_prompt_id = prompt_library["default_id"]
    wrapper_info = load_wrapper_prompt()
    use_wrapper = config.get("use_wrapper_prompt")
    if use_wrapper is None:
        use_wrapper = wrapper_info.get("enabled", True)
    wrapper_prompt = wrapper_info.get("content", "") if use_wrapper else ""

    print("OpenAI API Communicator CLI")
    print(
        "Commands: /model <id>, /system <text>, /prompt <id>, /prompts, /wrapper on|off, /new, /key <key>, /exit"
    )
    api_key = resolve_api_key(config, prefer_env=True)
    prompt_id = config.get("prompt_id") or default_prompt_id
    system_prompt = config.get("system_prompt")
    if not system_prompt:
        system_prompt = prompt_map.get(prompt_id, {}).get(
            "content", DEFAULT_SYSTEM_PROMPT
        )
    model = config.get("model", "")

    if not conversations:
        conversation = new_conversation(model=model)
        conversations = [conversation]
        active_id = conversation["id"]

    def get_active_conversation():
        for convo in conversations:
            if convo.get("id") == active_id:
                return convo
        return conversations[0]

    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            break
        if not line:
            continue
        if line in ("/exit", "/quit", "exit", "quit"):
            break
        if line == "/prompts":
            for prompt in prompt_library["prompts"]:
                print(f"{prompt['id']}: {prompt['name']}")
            continue
        if line.startswith("/prompt "):
            prompt_id = line.split(" ", 1)[1].strip()
            prompt = prompt_map.get(prompt_id)
            if not prompt:
                print("Unknown prompt id")
            else:
                system_prompt = prompt.get("content", DEFAULT_SYSTEM_PROMPT)
                print(f"Prompt set to {prompt_id}")
            continue
        if line.startswith("/model "):
            model = line.split(" ", 1)[1].strip()
            print(f"Model set to {model}")
            conversation = get_active_conversation()
            conversation["model"] = model
            models_used = conversation.setdefault("models_used", [])
            if model and model not in models_used:
                models_used.append(model)
            conversation["updated_at"] = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            )
            save_conversations(conversations, active_id)
            continue
        if line.startswith("/system "):
            system_prompt = line.split(" ", 1)[1].strip()
            prompt_id = ""
            print("System prompt updated")
            continue
        if line.startswith("/wrapper "):
            value = line.split(" ", 1)[1].strip().lower()
            if value in ("on", "true", "1", "yes"):
                use_wrapper = True
            elif value in ("off", "false", "0", "no"):
                use_wrapper = False
            else:
                print("Usage: /wrapper on|off")
                continue
            wrapper_prompt = wrapper_info.get("content", "") if use_wrapper else ""
            config["use_wrapper_prompt"] = use_wrapper
            save_config(config)
            print(f"Wrapper prompt {'enabled' if use_wrapper else 'disabled'}")
            continue
        if line.startswith("/key "):
            api_key = line.split(" ", 1)[1].strip()
            location = store_api_key(config, api_key)
            if location == "keyring":
                print("API key saved to system keyring")
            else:
                print("API key saved to config file")
            continue
        if line == "/new":
            conversation = new_conversation(model=model)
            conversations.append(conversation)
            active_id = conversation["id"]
            save_conversations(conversations, active_id)
            print("New chat started")
            continue

        if not model:
            print("Set a model first with /model <id>")
            continue

        conversation = get_active_conversation()
        conversation.setdefault("messages", []).append({"role": "user", "content": line})
        conversation["updated_at"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )
        if model:
            conversation["model"] = model
            models_used = conversation.setdefault("models_used", [])
            if model not in models_used:
                models_used.append(model)
        save_conversations(conversations, active_id)
        try:
            resolved_key = resolve_api_key(config, override=api_key, prefer_env=True)
            reply = send_chat(
                resolved_key,
                model,
                wrapper_prompt,
                system_prompt,
                list(conversation["messages"]),
            )
        except Exception as exc:
            print(f"Error: {exc}")
            continue
        print(reply)
        conversation["messages"].append({"role": "assistant", "content": reply})
        conversation["updated_at"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )
        save_conversations(conversations, active_id)

    config["model"] = model
    config["system_prompt"] = system_prompt
    config["prompt_id"] = prompt_id
    config["use_wrapper_prompt"] = use_wrapper
    save_config(config)


def main():
    parser = argparse.ArgumentParser(description="OpenAI API Communicator")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode")
    args = parser.parse_args()

    config = load_config()
    conversations, active_id = load_conversations(config)

    if args.cli:
        run_cli(config, conversations, active_id)
        return

    run_gui()


if __name__ == "__main__":
    main()
