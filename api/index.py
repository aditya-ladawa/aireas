from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from uuid import uuid4
import os
from pathlib import Path
from dotenv import load_dotenv
import xml.etree.ElementTree as ET

# Import necessary modules
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from qdrant_client import QdrantClient
from grobid_client.grobid_client import GrobidClient

# Import local functions and models
from api.qdrant_ops import connect_to_qdrant
from api.grobid_ops import connect_to_grobid
from api.helpers import *
from api.pydantic_models import QueryRequest  # Ensure you have the correct model definition
from typing import List

# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json")

# Embedding model
EMBEDDING_MODEL = GoogleGenerativeAIEmbeddings(model='models/text-embedding-004')

# Collection name
COLLECTION_NAME = 'aireas-local'

# GROBID CLIENT
grobid_client = connect_to_grobid()

# Qdrant client
qdrant_client = connect_to_qdrant()

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define directories for file uploads
static_dir = Path("api/static/files")
static_dir.mkdir(exist_ok=True)

metas_dir = "api/metas/"
os.makedirs(metas_dir, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/api/healthchecker")
def healthchecker():
    return {"status": "success", "message": "FastAPI and Next.js are integrated"}

@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Uploads PDF files, processes them with GROBID, and stores their embeddings."""
    # try:
    #     uploaded_files_info = await process_pdf_files_texts(files, qdrant_client, grobid_client, COLLECTION_NAME, EMBEDDING_MODEL, upload_dir_=static_dir, metas_dir_=metas_dir)
    #     return {"uploaded_files": uploaded_files_info}

    try:
        uploaded_files_info = await process_pdfs(files, qdrant_client, COLLECTION_NAME, EMBEDDING_MODEL, upload_dir_=static_dir)
        return {"uploaded_files": uploaded_files_info}


    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/retrieve')
def retrieve(query_request: QueryRequest):
    """Retrieves relevant PDF information based on the query."""
    try:
        # Get the embeddings for the query
        query_embeddings = EMBEDDING_MODEL.embed_query(query_request.query)

        # Query points from Qdrant
        search_result = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embeddings,
            with_payload=True,
            limit=query_request.top_k,
        )

        # Extracting necessary details
        results = []
        if hasattr(search_result, 'points'):
            for point in search_result.points:  # Access the points attribute
                results.append({
                    "id": point.id,
                    "score": point.score,
                    "pdf_id": point.payload.get('pdf_id', 'N/A'),  # Use get to avoid KeyError
                    "text": point.payload.get('text', 'N/A'),
                })

        return {"points": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

