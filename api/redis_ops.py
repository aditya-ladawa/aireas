import uuid
from datetime import datetime
import redis.asyncio as redis
import json

redis_client = None  # Global Redis client for shared use

async def initialize_redis():
    """
    Initialize the Redis connection.
    """
    global redis_client
    if not redis_client:
        redis_client = redis.Redis.from_url(
            "redis://localhost:6379", decode_responses=True,
        )
        print("Redis connection initialized.")


async def close_redis_connection():
    """
    Gracefully close the Redis connection.
    """
    global redis_client
    if redis_client:
        await redis_client.aclose()
        redis_client = None
        print("Redis connection closed.")



async def add_conversation(user_id: str, email: str, name: str, description: str, topic: str):
    """
    Add a conversation to the Redis database with the specified structure.
    """
    user_key = f"user:{user_id}"
    conversation_id = str(uuid.uuid4())  # Unique conversation ID
    timestamp = datetime.now().isoformat()

    # Ensure the user exists with their email
    await redis_client.hset(user_key, mapping={"user_email": email})

    # Structure for the conversation
    conversation_data = {
        "name": name,
        "description": description,
        "timestamp": timestamp,
        "topic": topic,
        "files": json.dumps({})
    }

    # Add the conversation under 'user:{user_id}:conversations'
    conversations_key = f"{user_key}:conversations"
    await redis_client.hset(conversations_key, conversation_id, json.dumps(conversation_data))

    return {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "conversation_data": conversation_data,
    }

