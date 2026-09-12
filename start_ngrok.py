import os
import time
from pyngrok import ngrok

def start_tunnel():
    print("Starting Ngrok tunnel for port 8000...")
    # Open a HTTP tunnel on the default port 80 (or specify a port, e.g., 8000)
    public_url = ngrok.connect(8000).public_url
    
    print("\n" + "="*60)
    print("🚀 NGROK TUNNEL STARTED SUCCESSFULLY! 🚀")
    print("="*60)
    print("Please copy the URL below and paste it into your Twilio Sandbox Settings:")
    print(f"\n--->  {public_url}/webhook/twilio  <---\n")
    print("="*60)
    print("Keeping tunnel open. Do not close this terminal...")
    
    try:
        # Block until CTRL-C or some other terminating event
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Closing tunnel...")
        ngrok.kill()

if __name__ == '__main__':
    start_tunnel()
