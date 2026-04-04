import streamlit_authenticator as stauth
import streamlit as st

authenticator = stauth.Authenticate(
    {"usernames": {"test": {"name": "Test", "password": "password", "email": "test@test.com"}}},
    "cookie",
    "key"
)

try:
    # login returns authentication_status in newer versions, or maybe something else?
    # but the line in user's app is unpacking 3 values.
    # In 0.3.0 it returned (name, authentication_status, username).
    # Maybe 0.4.x CHANGED it?
    pass
except Exception as e:
    print(f"Error: {e}")
