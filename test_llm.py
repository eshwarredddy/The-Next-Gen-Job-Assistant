import asyncio
from main import ai_client, SYSTEM_PROMPT

async def test_llm():
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "hi"}
    ]
    try:
        response = await ai_client.chat.completions.create(
            model="meta/llama3-70b-instruct",
            messages=messages,
            temperature=0.7,
            max_tokens=250
        )
        print("SUCCESS:", response.choices[0].message.content)
    except Exception as e:
        print("ERROR:", e)

asyncio.run(test_llm())
