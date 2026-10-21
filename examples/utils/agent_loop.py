import json


# --- Agent loop ---
def agent_loop(api_key, model, provider, tool_schema, tool_registry, messages):
    tools = [tool_schema]
    messages = messages

    while True:
        response = provider.chat(
            model=model,
            messages=messages,
            tools=tools
        )

        messages.append(response["message"])

        tool_calls = response["message"].get("tool_calls")

        if not tool_calls:
            final_output = response["message"]["content"]
            return final_output

        for call in tool_calls:
            name = call["function"]["name"]
            args = call["function"]["arguments"]

            tool_func = tool_registry[name]
            result = tool_func(**args, api_key=api_key)

            messages.append({
                "role": "tool",
                "content": json.dumps(result),
                "name": name
            })
