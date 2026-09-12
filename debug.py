import asyncio
from main import generate_cold_email, send_sms, SessionLocal

async def test():
    print("Testing generate_cold_email...")
    try:
        body = await generate_cold_email("test resume", "test job")
        print("LLM SUCCESS:", body)
    except Exception as e:
        print("LLM FAILED:", e)

    print("Testing send_sms...")
    try:
        sid = send_sms("+918341847261", "Test SMS")
        print("SMS SUCCESS:", sid)
    except Exception as e:
        print("SMS FAILED:", e)

if __name__ == "__main__":
    asyncio.run(test())
