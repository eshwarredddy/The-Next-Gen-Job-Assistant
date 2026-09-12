import gmail_service

if __name__ == "__main__":
    res = gmail_service.send_email(
        to_email="test@example.com",
        subject="Test subject",
        body="Test body"
    )
    print("Result:", res)
