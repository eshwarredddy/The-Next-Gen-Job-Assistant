import gmail_service

try:
    gmail_service.send_email(
        to_email="test@example.com",
        subject="Test from backend",
        body="This is a test."
    )
    print("Success!")
except Exception as e:
    import traceback
    traceback.print_exc()
