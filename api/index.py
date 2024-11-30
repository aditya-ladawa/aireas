from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Response, Request, Query, status

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

from api.qdrant_cloud_ops import process_pdfs, qclient_, EMBEDDING_MODEL

# sql_ops imports
from api.sql_ops import init_db, create_user, get_user_by_email, verify_password, generate_jwt_token, validate_password_strength, get_user_by_id
from fastapi.responses import JSONResponse
from api.pydantic_models import *

from api.chat_handlers import assign_chat_topic_chain

from fastapi.security import OAuth2PasswordBearer

import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from jwt import decode

from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timedelta


from sqlalchemy.exc import SQLAlchemyError

import re

import traceback


from api.redis_ops import add_conversation, initialize_redis, close_redis_connection


load_dotenv()

# Services
SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
ALGORITHM = "HS256"
EMBEDDING_MODEL = EMBEDDING_MODEL
COLLECTION_NAME = 'aireas-cloud'
qdrant_client = qclient_
APIS = os.path.join(os.getcwd(), 'api')


# Initialize FastAPI
app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json", debug=True)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://localhost:3000"],  # Update as per your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define the UserAuthMiddleware class
class UserAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, secret_key: str, algorithm: str):
        super().__init__(app)
        self.secret_key = secret_key
        self.algorithm = algorithm

    async def dispatch(self, request: Request, call_next):
        unprotected_routes = [
            "/api/login",
            "/api/signup",
            "/api/logout",
            "/api/docs",
            "/api/openapi.json",
        ]

        # Allow unprotected routes without authentication
        for route in unprotected_routes:
            if re.fullmatch(route, request.url.path):
                response = await call_next(request)
                return response

        # Example regex for routes to skip authentication
        if re.fullmatch(r"/api/.*/\w+", request.url.path):
            response = await call_next(request)
            return response

        # Extract token from cookies
        token = request.cookies.get("auth_token")
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")

        try:
            payload = decode(token, self.secret_key, algorithms=[self.algorithm])
            exp = payload.get("exp")
            if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
                raise HTTPException(status_code=401, detail="Token has expired")

            # Add user data to request state
            user = {
                "user_id": payload.get("user_id"),
                "email": payload.get("email"),
            }
            request.state.user = user

        except ExpiredSignatureError as e:
            raise HTTPException(status_code=401, detail=f"Token expired: {str(e)}")
        except InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
        except DecodeError as e:
            raise HTTPException(status_code=400, detail=f"Malformed token: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

        # Continue to the next middleware or route handler
        response = await call_next(request)
        return response

# Add UserAuthMiddleware to the application
app.add_middleware(
    UserAuthMiddleware,
    secret_key=SECRET_KEY,
    algorithm=ALGORITHM,
)



@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Custom handler for HTTP exceptions to structure the error response.
    """
    # Provide detailed error information for debugging
    error_detail = {
        "detail": exc.detail,
        "status_code": exc.status_code,
        "message": "An error occurred during the request.",
    }

    # Include stack trace if in debug mode
    if app.debug:
        error_detail["stack_trace"] = traceback.format_exc()

    return JSONResponse(
        status_code=exc.status_code,
        content=error_detail,
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Custom handler for uncaught exceptions.
    """
    error_detail = {
        "detail": str(exc),
        "status_code": 500,
        "message": "Internal server error occurred.",
    }

    # Include stack trace if in debug mode
    if app.debug:
        error_detail["stack_trace"] = traceback.format_exc()

    return JSONResponse(
        status_code=500,
        content=error_detail,
    )

# # Define directories for file uploads
# static_dir = Path("api/static/")
# static_dir.mkdir(exist_ok=True)

# metas_dir = "api/metas/"
# os.makedirs(metas_dir, exist_ok=True)

# # Mount static files
# app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Initialize the sql database at startup
@app.on_event("startup")
async def sql_startup_event():
    await init_db()
    print('\nStarted SQL db')

# Initialize the redis database at startup
@app.on_event("startup")
async def redis_startup_event():
    await initialize_redis()

@app.on_event("shutdown")
async def redis_shutdown_event():
    await close_redis_connection()


def get_authenticated_user(request: Request):
    if not request.state.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return request.state.user


@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...), current_user: dict = Depends(get_authenticated_user)):
    """
    Upload and process PDF files for the current authenticated user.
    """
    try:
        # Retrieve user information from the current authenticated user
        user_id = current_user.get("user_id")
        email = current_user.get("email")
        if not user_id or not email:
            raise HTTPException(status_code=401, detail="User authentication failed.")

        # Define the user's directory
        user_storage_base = os.path.join(APIS, "users_storage")
        user_dir = os.path.join(user_storage_base, user_id)

        # Process uploaded files
        result = await process_pdfs(
            files=files,
            qclient_=qclient_,
            collection_name="aireas-cloud",
            emb_model=EMBEDDING_MODEL,
            user_id=user_id,
            email=email,
            user_dir=user_dir,
        )

        return result

    except HTTPException as e:
        print(f"HTTPException: {e.detail}")
        raise
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@app.get("/api/get_uploaded_files")
async def get_files(current_user: dict = Depends(get_authenticated_user)):
    try:
        # Retrieve user-specific storage directory
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User authentication failed.")

        user_storage_base = os.path.join(APIS, "users_storage")
        user_dir = os.path.join(user_storage_base, user_id)

        if not os.path.exists(user_dir):
            return JSONResponse(content={"files": [], "message": "No files found."}, status_code=200)

        files = [
            file for file in os.listdir(user_dir) if os.path.isfile(os.path.join(user_dir, file))
        ]

        return JSONResponse(content={"files": files}, status_code=200)

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post('/api/retrieve')
def retrieve(query_request: QueryRequest, current_user: dict = Depends(get_authenticated_user)):
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

    try:
        new_user = await create_user(
            user_name=user.name.strip(),
            raw_password=user.password,
            email=user.email.strip().lower(),
        )

        return JSONResponse(
            content={
                "message": f"User {new_user.user_name} successfully registered.",
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during signup. Please try again later.",
        )

@app.post("/api/login", status_code=200)
async def login(user: UserLogin, response: Response):
    try:
        db_user = await get_user_by_email(user.email.strip().lower())
        if db_user is None or not verify_password(user.password, db_user.password):
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        token = generate_jwt_token(user_id=db_user.user_id, email=db_user.email)

        response.set_cookie(
            key="auth_token",
            value=token,
            httponly=True,
            secure=False,
            samesite='Strict'
        )

        return {"message": "Login successful"}

    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get('/api/get_auth_user')
async def get_active_user(current_user: dict = Depends(get_authenticated_user)):
    return {'user': current_user}


@app.post("/api/logout")
async def logout(response: Response):
    try:
        response.set_cookie(
            key="auth_token",
            value="", 
            expires="Thu, 01 Jan 1994 00:00:00 GMT",
            max_age=0, 
            httponly=True,
            secure=False,
            samesite="Strict",
            path="/",
        )
        return {"message": "Logout successful"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during logout: {str(e)}")


@app.post('/api/add_conversation')
async def add_conversation_route(request: AssignTopic, current_user: dict = Depends(get_authenticated_user)):
    """
    API route to add a conversation.
    """
    try:
        # Extract user details from the authenticated user
        user_id = current_user.get("user_id")
        email = current_user.get("email")

        if not user_id or not email:
            raise HTTPException(status_code=400, detail="User ID or email is missing from the request.")

        # Extract conversation details from the request body
        name = request.conversation_name
        description = request.conversation_description

        if not name.strip() or not description.strip():
            raise HTTPException(status_code=400, detail="Both conversation_name and conversation_description are required.")

        assigned_topic = assign_chat_topic_chain.invoke(description)

        # Add conversation to Redis
        result = await add_conversation(user_id, email, name, description, assigned_topic)

        # Return success message
        return {
            "message": "Conversation added successfully",
            "conversation_id": result["conversation_id"],
            "assigned_topic": assigned_topic
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get('/api/user_conversations')
async def get_conversations_route(current_user: dict = Depends(get_authenticated_user)):
    """
    API route to retrieve all conversations for a user.
    """
    try:
        # Extract user details
        user_id = current_user["user_id"]

        # Retrieve conversations from Redis
        conversations = await get_user_conversations(user_id)

        return {"conversations": conversations}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


