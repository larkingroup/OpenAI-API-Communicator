import os

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


def build_messages(wrapper_prompt, system_prompt, messages):
    output = []
    if wrapper_prompt:
        output.append({"role": "system", "content": wrapper_prompt})
    if system_prompt:
        output.append({"role": "system", "content": system_prompt})
    output.extend(messages)
    return output


def send_chat(api_key, model, wrapper_prompt, system_prompt, messages):
    if OpenAI is None:
        raise RuntimeError("openai package not installed")
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("API key is missing")

    client = OpenAI(api_key=api_key)
    use_chat = "gpt-3.5" in model or model.endswith("-turbo")
    if use_chat:
        response = client.chat.completions.create(
            model=model,
            messages=build_messages(wrapper_prompt, system_prompt, messages),
        )
        return response.choices[0].message.content or ""

    response = client.responses.create(
        model=model,
        input=build_messages(wrapper_prompt, system_prompt, messages),
    )
    text = getattr(response, "output_text", "")
    if text:
        return text
    try:
        return response.output[0].content[0].text
    except Exception:
        return ""
