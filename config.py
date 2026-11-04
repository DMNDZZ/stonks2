"""Runtime configuration supplied through environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_PROXY_URL = os.getenv("BOT_PROXY_URL") or None
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "")

INVENTORY_SHEET = os.getenv("INVENTORY_SHEET", "")
PRICES_SHEET = os.getenv("PRICES_SHEET", "")
CONTRACTS_SHEET = os.getenv("CONTRACTS_SHEET", "")
RENTALS_SHEET = os.getenv("RENTALS_SHEET", "")
CLIENTS_SHEET = os.getenv("CLIENTS_SHEET", "")

DAY_END_TIME = int(os.getenv("DAY_END_TIME") or "21")

GOOGLE_TYPE = os.getenv("GOOGLE_TYPE", "service_account")
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID", "")
GOOGLE_PRIVATE_KEY_ID = os.getenv("GOOGLE_PRIVATE_KEY_ID", "")
GOOGLE_PRIVATE_KEY = os.getenv("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n")
GOOGLE_CLIENT_EMAIL = os.getenv("GOOGLE_CLIENT_EMAIL", "")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_AUTH_URI = os.getenv("GOOGLE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth")
GOOGLE_TOKEN_URI = os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token")
GOOGLE_AUTH_PROVIDER_X509_CERT_URL = os.getenv(
    "GOOGLE_AUTH_PROVIDER_X509_CERT_URL",
    "https://www.googleapis.com/oauth2/v1/certs",
)
GOOGLE_CLIENT_X509_CERT_URL = os.getenv("GOOGLE_CLIENT_X509_CERT_URL", "")
GOOGLE_UNIVERSE_DOMAIN = os.getenv("GOOGLE_UNIVERSE_DOMAIN", "googleapis.com")
