import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly"
]

def main():
    if not os.path.exists("credentials.json"):
        print("ERROR: credentials.json is missing in current directory.")
        return
        
    print("\n--- GMAIL AUTHORIZATION GENERATOR ---")
    print("This will open a browser window or generate a local link to authenticate Gmail.")
    print("Once authorized, token.json will be saved with a permanent offline refresh token.")
    
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    # Run local server on port 0
    try:
        creds = flow.run_local_server(port=0, open_browser=True)
        with open("token.json", "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        print("\nSUCCESS: token.json created successfully!")
        print("Your bot can now send emails and check replies headlessly.")
    except Exception as e:
        print(f"Error during authorization: {e}")

if __name__ == "__main__":
    main()
