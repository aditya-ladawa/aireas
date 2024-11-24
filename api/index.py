from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from uuid import uuid4
import os
from pathlib import Path
from dotenv import load_dotenv

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from qdrant_client import QdrantClient

from typing import List

from api.qdrant_cloud_ops import process_pdfs, qclient_, EMBEDDING_MODEL, QueryRequest

# sql_ops imports
from api.sql_ops import init_db, create_user, get_user_by_email, verify_password, UserCreate, UserLogin, generate_jwt_token, validate_password_strength
from fastapi.responses import JSONResponse


# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json")

# Initialize the database at startup
@app.on_event("startup")
async def startup_event():
    await init_db()

EMBEDDING_MODEL = EMBEDDING_MODEL
COLLECTION_NAME = 'aireas-cloud'
qdrant_client = qclient_

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


@app.post("/api/signup", status_code=201)
async def signup(user: UserCreate):
    # Check if email already exists
    existing_user = await get_user_by_email(user.email.lower())
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="This email is already registered. Please log in.",
        )
    
    # Validate password strength
    if not validate_password_strength(user.password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 8 characters, including an uppercase letter, a number, and a special character.",
        )
    
    # Create the new user
    try:
        new_user = await create_user(
            user_name=user.name.strip(),
            raw_password=user.password,
            email=user.email.strip().lower(),
        )
        return JSONResponse(
            content={"message": f"User {new_user.user_name} successfully registered."}
        )
    except Exception as e:
        print(f"Error during signup: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during signup. Please try again later.",
        )


@app.post("/api/login", status_code=200)
async def login(user: UserLogin):
    """
    Authenticate a user. Validates email and password, and returns a JWT token upon success.
    """
    # Fetch user by email
    db_user = await get_user_by_email(user.email.strip().lower())
    if not db_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )
    
    # Verify password
    if not await verify_password(user.password, db_user.password):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )
    
    # Generate JWT token
    try:
        token = generate_jwt_token(user_id=db_user.user_id, email=db_user.email)
        return JSONResponse(
            content={"message": "Login successful", "token": token}
        )
    except Exception as e:
        # Log the exception if necessary
        print(f"Error during login: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during login. Please try again later.",
        )