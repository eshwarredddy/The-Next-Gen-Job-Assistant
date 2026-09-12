import requests
import json
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    apollo_api_key: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

def test_apollo():
    url = "https://api.apollo.io/v1/mixed_people/search"
    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "Api-Key": settings.apollo_api_key  # According to Apollo docs, it's often passed in Api-Key or X-Api-Key or Cache-Control. Let's use X-Api-Key if that failed, wait, let me just pass it in X-Api-Key or Cache-Control... wait, error says X-Api-Key
    }
    # Wait, the error said "API key must be passed in the Cache-Control header"? No, "API key must be passed in the X-Api-Key header for security reasons"
    # Actually wait. Let me just use Cache-Control. No, I will use Cache-Control.
    
    headers["X-Api-Key"] = settings.apollo_api_key
    
    data = {
        "q_keywords": "artificial intelligence startup",
        "person_titles": ["founder", "ceo", "co-founder"],
        "organization_num_employees_ranges": ["1,10", "11,50", "51,200"],
        "contact_email_status": ["verified"],
        "page": 1,
        "per_page": 2
    }
    
    print("Testing Apollo API...")
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        results = response.json()
        print("Success! Found", len(results.get("people", [])), "people.")
        for person in results.get("people", []):
            fname = person.get("first_name")
            lname = person.get("last_name")
            email = person.get("email")
            org = person.get("organization", {})
            company = org.get("name")
            print(f"- {fname} {lname} | {email} | {company}")
    else:
        print("Error:", response.status_code, response.text)

if __name__ == "__main__":
    test_apollo()
