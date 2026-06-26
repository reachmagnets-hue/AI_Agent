import asyncio
from app.services.ai_reviewer import analyze_inbox_message

async def main():
    chat1 = """
    Sales: Hi John, wanted to see if you have time next week to discuss our automation tools?
    John: Yes, that sounds interesting. I'm available next Tuesday at 2 PM EST. Let's do it.
    """
    
    chat2 = """
    Sales: Hi Sarah, wanted to follow up on my previous message.
    Sarah: Please remove me from your list. Not interested.
    """
    
    chat3 = """
    Sales: Hi Mark, are you open to exploring AI callers?
    Mark: I might be. Send me a one-pager to review first.
    """
    
    print("Test 1 (Expected Booking):")
    res1 = await analyze_inbox_message(chat1)
    print(res1)
    
    print("\nTest 2 (Expected Not Interested):")
    res2 = await analyze_inbox_message(chat2)
    print(res2)
    
    print("\nTest 3 (Expected Interested):")
    res3 = await analyze_inbox_message(chat3)
    print(res3)

if __name__ == "__main__":
    asyncio.run(main())
