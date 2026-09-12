import os
import asyncio
from openai import AsyncOpenAI
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    nvidia_api_key: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

ai_client = AsyncOpenAI(
    api_key=settings.nvidia_api_key,
    base_url="https://integrate.api.nvidia.com/v1",
    timeout=10.0
)

async def test():
    try:
        response = await ai_client.models.list()
        for m in response.data:
            print(m.id)
    except Exception as e:
        print("Error:", repr(e))

if __name__ == "__main__":
    asyncio.run(test())
