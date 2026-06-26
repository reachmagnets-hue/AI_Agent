import asyncio
import os
import sys

# Ensure backend path is in Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.utils.linkedin_generator import generate_linkedin_message

async def main():
    print("Testing LinkedIn message generation template...")
    result = await generate_linkedin_message("Sarah Connor", "Cyberdyne Systems", "robotics & artificial intelligence")
    print("\n--- Generated Message Start ---")
    print(result)
    print("--- Generated Message End ---\n")
    print(f"Message length: {len(result)} characters")

if __name__ == "__main__":
    asyncio.run(main())
