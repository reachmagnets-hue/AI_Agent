import asyncio
import sys
import os

# Adjust path to import app correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.retell_service import register_webhook
from app.core.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    url = f"{settings.BASE_URL}/api/retell/webhook"
    result = asyncio.run(register_webhook(url))
    print(f"Webhook registered: {url}")
    print(result)
