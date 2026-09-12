import asyncio
from fastapi import Request
from main import twilio_webhook, SessionLocal

async def test():
    db = SessionLocal()
    # Mock request
    class MockRequest:
        async def form(self):
            return {"Body": "SEND 1", "From": "+918341847261"}
            
    req = MockRequest()
    try:
        res = await twilio_webhook(req, db)
        print("Success:", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test())
