from typing import List
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import fitz  # PyMuPDF for PDF processing
import asyncio
import os
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from api.qdrant_ops import connect_to_qdrant
from contextlib import asynccontextmanager
from api.helpers import *

# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json")

# Qdrant init
# Startup event to initialize the Qdrant client
@app.on_event("startup")
async def startup_event():
    client = connect_to_qdrant()
    app.state.qdrant_client = client

# Shutdown event to close the Qdrant client
@app.on_event("shutdown")
async def shutdown_event():
    client = app.state.qdrant_client
    print("Shutting down Qdrant client")
    client.close() 

# Embedding model
embedding_model = GoogleGenerativeAIEmbeddings(model='models/text-embedding-004')

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
async def upload_pdfs(files: List[UploadFile] = File(...)):
    client = app.state.qdrant_client  # Access the Qdrant client here
    uploaded_files_names = await process_pdfs(files, client_=client,collection_name='aireas-local')
    return uploaded_files_names


