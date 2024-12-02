from qdrant_client import QdrantClient
import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from uuid import uuid4
import fitz
from langchain.text_splitter import RecursiveCharacterTextSplitter
from qdrant_client.http import models
from langchain_qdrant import QdrantVectorStore
from langchain.chains.query_constructor.base import AttributeInfo
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain_groq import ChatGroq
from typing import Dict, List, TypedDict
from langchain_core.documents import Document
from pydantic import BaseModel
import shutil
import aiofiles
from qdrant_client.http.models import UpdateStatus
from datetime import datetime
import aiofiles



load_dotenv()




llm_for_retrievel = ChatGroq(model='llama-3.1-70b-versatile')

EMBEDDING_MODEL = GoogleGenerativeAIEmbeddings(model='models/text-embedding-004')
QDRANT_API_KEY = os.environ.get('QDRANT_API_KEY')
URL = os.environ.get('QDRANT_URL')



_qdrant_client = None

def connect_to_qdrant():
    global _qdrant_client
    if _qdrant_client is None:
        try:
            _qdrant_client = QdrantClient(url=URL, api_key=QDRANT_API_KEY)
            print('\nStarted Qdrant client.')

            existing_collections = _qdrant_client.get_collections().collections
            if "aireas-cloud" not in [collection.name for collection in existing_collections]:
                _qdrant_client.create_collection(
                    collection_name="aireas-cloud",
                    vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
                )
                print("Collection 'aireas-cloud' created successfully.\n")

                _qdrant_client.create_payload_index(
                    collection_name="aireas-cloud",
                    field_name="user_id",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )

                _qdrant_client.create_payload_index(
                    collection_name="aireas-cloud",
                    field_name="conversation_id",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )

                print("\nIndex created on 'user_id' and 'conversation_id' fields for efficient filtering.\n")
            else:
                print("Collection 'aireas-cloud' already exists.")

        except Exception as e:
            print(f"Connection error: {e}")
            _qdrant_client = None
    return _qdrant_client


async def process_pdfs(files, qclient_, collection_name, emb_model, user_id, email, conversation_dir, conversation_id):
    """
    Process uploaded PDF files, extract text, generate embeddings, and upsert them into Qdrant.
    """
    uploaded_files_info = {}
    errors = []

    # Ensure the conversation directory exists
    os.makedirs(conversation_dir, exist_ok=True)

    for file in files:
        filename_lower = file.filename.lower()
        file_path = os.path.join(conversation_dir, filename_lower)  # Save in the conversation directory

        try:
            # Check if the file already exists in the specified path
            if os.path.exists(file_path):
                print(f"File {filename_lower} already exists. Skipping vectorization.")
                continue

            # Save the file to the specified path
            content = await file.read()
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)
            print(f"PDF saved to: {file_path}")
        except Exception as e:
            error_message = f"Failed to save {filename_lower}: {str(e)}"
            print(error_message)
            errors.append({"file": filename_lower, "error": error_message})
            continue

        try:
            # Extract text from the PDF
            pdf_text = extract_text_from_pdf(file_path)
            if not pdf_text.strip():
                raise ValueError("The PDF is empty or text could not be extracted.")

            # Split text into chunks
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=2100, chunk_overlap=210)
            text_chunks = text_splitter.split_text(pdf_text)

            # Generate embeddings for the chunks
            embeddings = emb_model.embed_documents(text_chunks)

            # Prepare points for Qdrant
            pdf_id = filename_lower
            points = [
                models.PointStruct(
                    id=str(uuid4()),
                    payload={
                        "metadata": {
                            "pdf_id": pdf_id,
                            "associated_user": user_id,
                            "associated_user_email": email,
                            "associated_conversation_id": conversation_id
                        },
                        "text": chunk,
                    },
                    vector=embedding,
                )
                for chunk, embedding in zip(text_chunks, embeddings)
            ]

            # Upsert points into Qdrant
            upsert_response = qclient_.upsert(collection_name=collection_name, points=points)

            if upsert_response.status != UpdateStatus.COMPLETED:
                raise RuntimeError(f"Upsert failed for {filename_lower}. Response: {upsert_response}")

        except Exception as e:
            error_message = f"Error processing {filename_lower}: {str(e)}"
            print(error_message)
            if os.path.exists(file_path):
                os.remove(file_path)
            errors.append({"file": filename_lower, "error": error_message})
            continue

        # Capture the timestamp after successful processing
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        uploaded_files_info[filename_lower] = {
            "file_name": filename_lower,
            "total_chunks": len(text_chunks),
            "upsert_response": upsert_response,
            "file_path": file_path,
            "timestamp": timestamp,
        }

    # If there are any errors, print them
    if errors:
        print(errors)

    return {"uploaded_files": uploaded_files_info}

    
def extract_text_from_pdf(file_path) -> str:
    pdf_document = fitz.open(file_path)
    text = ""
    for page in pdf_document:
        text += page.get_text()
    pdf_document.close()
    return text


qclient_ = connect_to_qdrant()

if qclient_:
    qdrant_vector_store = QdrantVectorStore.from_existing_collection(
    collection_name="aireas-cloud",
    embedding=EMBEDDING_MODEL,
    api_key=QDRANT_API_KEY,
    url=URL,
    # prefer_grpc=True,
    content_payload_key="text",
    metadata_payload_key="metadata"
)


def parse_documents(documents: List[Document]) -> List[Dict[str, str]]:
    parsed_output = []
    for doc in documents:
        pdf_id = doc.metadata.get('pdf_id', 'Unknown')
        page_content = doc.page_content
        parsed_output.append({'pdf_id': pdf_id, 'page_content': page_content})
    return parsed_output

def initialize_selfquery_retriever(llm, qdrant_vector_store):
    """
    Initialize and return a SelfQueryRetriever instance configured to work with an existing Qdrant vector store.

    Args:
        llm: The language model instance to use for querying.
        qdrant_vector_store (QdrantVectorStore): The already initialized QdrantVectorStore instance.

    Returns:
        SelfQueryRetriever: Configured retriever instance.
    """
    metadata_field_info = [
        AttributeInfo(
            name="pdf_id",
            description="The name of the research paper which is in .pdf filetype.",
            type="string",
        ),
    ]
    document_content_description = 'texts of several research papers, academic papers, and scholarly articles.'

    retriever = SelfQueryRetriever.from_llm(
            llm=llm,
        vectorstore=qdrant_vector_store,
        document_contents=document_content_description,
        metadata_field_info=metadata_field_info,
        enable_limit=True,
        verbose=True
    )
    retriever = retriever | parse_documents

    return retriever 


# qdrant_retriever = initialize_selfquery_retriever(llm=llm_for_retrievel, qdrant_vector_store=qdrant_vector_store)

