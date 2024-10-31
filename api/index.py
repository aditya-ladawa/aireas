from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import Depends
from typing import List, Dict
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import fitz  # PyMuPDF for PDF processing
import os
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from api.qdrant_ops import connect_to_qdrant
from api.helpers import *
from api.pydantic_models import *

# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json")

# Qdrant client
@app.on_event("startup")
async def startup_event():
    client = connect_to_qdrant()
    app.state.qdrant_client = client

@app.on_event("shutdown")
async def shutdown_event():
    client = app.state.qdrant_client
    if client:
        print("Shutting down Qdrant client")
        client.close()

# Qdrant client
def get_qdrant_client():
    return app.state.qdrant_client

# Embedding model
EMBEDDING_MODEL = GoogleGenerativeAIEmbeddings(model='models/text-embedding-004')

# Collection name
COLLECTION_NAME = 'aireas-local'

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define static directory for PDF uploads
static_dir = Path("api/static")
static_dir.mkdir(parents=True, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/api/healthchecker")
def healthchecker():
    return {"status": "success", "message": "FastAPI and Next.js are integrated"}

@app.post("/upload-pdfs/")
async def upload_pdfs(files: List[UploadFile] = File(...), client=Depends(get_qdrant_client)):
    uploaded_files_names = await process_pdfs(files, client_=client, collection_name=COLLECTION_NAME, emb_model=EMBEDDING_MODEL)
    return uploaded_files_names

@app.post('/api/retrieve')
def retrieve(query_request: QueryRequest, client=Depends(get_qdrant_client)):
    try:
        # Get the embeddings for the query
        query_embeddings = EMBEDDING_MODEL.embed_query(query_request.query)

        # Query points from Qdrant
        search_result = client.query_points(
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
                    "pdf_id": point.payload.get('pdf_id'),  # Use get to avoid KeyError
                    "text": point.payload.get('text'),
                })

        return {"points": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))