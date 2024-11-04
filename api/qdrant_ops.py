from qdrant_client import QdrantClient
from qdrant_client.http import models

def connect_to_qdrant():
    try:
        connection = QdrantClient("http://localhost:6333")

        if connection:
            print('Started Qdrant client.')
        
        # Check if the collection already exists
        existing_collections = connection.get_collections().collections
        if "aireas-local" not in [collection.name for collection in existing_collections]:
            connection.create_collection(
                collection_name="aireas-local",
                vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
            )
            print("Collection 'aireas-local' created successfully.")
        else:
            print("Collection 'aireas-local' already exists.")
        
        return connection
    except Exception as e:
        print(f"Connection error: {e}")
        return None