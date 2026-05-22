import asyncio
import sys
import os

# Adjust path to import app correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.retell_service import setup_retell_agent

if __name__ == "__main__":
    result = asyncio.run(setup_retell_agent())
    print("\nRetell agent setup complete!")
    print("Add these IDs to your .env file now.")
