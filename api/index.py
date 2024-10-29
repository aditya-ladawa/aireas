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
from api.pinecone_operations import PineconeOperations

# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json")

# Pinecone operations
pinecone_ops = PineconeOperations(dimension=768, index_name="aireas-index")


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

async def process_pdf(file: UploadFile):
    try:
        # Save PDF to static folder
        file_path = static_dir / file.filename
        with open(file_path, "wb") as pdf_file:
            pdf_file.write(await file.read())

        # Extract text from the PDF
        pdf_text = ""
        with fitz.open(file_path) as pdf:
            for page in pdf:
                pdf_text += page.get_text()

        # Split text into chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = text_splitter.split_text(pdf_text)

        # Generate embeddings for each chunk
        embeddings = [embedding_model.embed_query(chunk) for chunk in chunks]
        embedding_dim = len(embeddings[0]) if embeddings else 0

        # Upsert vectors to Pinecone
        pdf_id = file.filename.split('.')[0]  # Unique PDF ID
        response = pinecone_ops.upsert_pdf_vectors(pdf_id=pdf_id, filename=file.filename, vectors=embeddings)
        upserted_count = response.upserted_count if hasattr(response, 'upserted_count') else 0

        
        return {
            "filename": file.filename,
            "embedding_dim": embedding_dim,
            "path": str(file_path),
            "upsert_response": upserted_count
        }
    except Exception as e:  
        # Log the error or handle it as necessary
        return {
            "error": str(e),
            "filename": file.filename
        }



@app.post("/upload_pdfs")
async def upload_pdfs(files: List[UploadFile] = File(...)):
    # Process each PDF in parallel
    tasks = [process_pdf(file) for file in files]
    results = await asyncio.gather(*tasks)

    # Return a summary of each file's processing status
    response_data = []
    for result in results:
        if "error" in result:
            response_data.append({
                "filename": result["filename"],
                "error": result["error"],
            })
        else:
            response_data.append({
                "filename": result["filename"],
                "embedding_dim": result["embedding_dim"],
                "path": result["path"],
                "upsert_count": result['upsert_response']
            })

    return JSONResponse(content={"status": "success", "data": response_data})

