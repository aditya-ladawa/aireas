from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Response, Request, Query, status, WebSocket, WebSocketDisconnect

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

from langchain_core.messages import HumanMessage, BaseMessage, AIMessage, ToolMessage

from typing import List

from api.qdrant_cloud_ops import process_pdfs, qclient_, EMBEDDING_MODEL

# sql_ops imports
from api.sql_ops import init_db, create_user, get_user_by_email, verify_password, generate_jwt_token, validate_password_strength, get_user_by_id
from fastapi.responses import JSONResponse
from api.pydantic_models import *

from api.chat_handlers import assign_chat_topic_chain, llm, react_agent

from fastapi.security import OAuth2PasswordBearer

import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from jwt import decode

from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timedelta


from sqlalchemy.exc import SQLAlchemyError

import re

import traceback


from api.redis_ops import add_conversation, initialize_redis, close_redis_connection, fetch_user_conversations, fetch_conversation, update_conversation_files


from fastapi.responses import FileResponse

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
    token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = payload.get("exp")
        
        if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")

        return {
            "user_id": payload.get("user_id"),
            "email": payload.get("email"),
        }

    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except DecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed token")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {str(e)}")


@app.post("/api/upload/{conversation_id}")
async def upload_files(conversation_id: str, files: List[UploadFile] = File(...), current_user: dict = Depends(get_authenticated_user)):
    """
    Upload and process PDF files for the current authenticated user.
    """
    try:
        user_id = current_user.get("user_id")
        email = current_user.get("email")  # Assuming email is in the user dict

        if not user_id or not email:
            raise HTTPException(status_code=401, detail="User authentication failed.")

        # Define the user's directory
        user_storage_base = os.path.join(APIS, "users_storage")
        user_dir = os.path.join(user_storage_base, user_id)
        conversation_dir = os.path.join(user_dir, conversation_id)

        os.makedirs(conversation_dir, exist_ok=True)

        # Process uploaded files
        result = await process_pdfs(
            files=files,
            qclient_=qclient_,
            collection_name="aireas-cloud",
            emb_model=EMBEDDING_MODEL,
            user_id=user_id,
            email=email,
            conversation_dir=conversation_dir,
            conversation_id=conversation_id
        )

        # Debugging: Print the result to inspect
        print("Result from process_pdfs:", result)

        if result and "uploaded_files" in result and result["uploaded_files"]:
            uploaded_files = result["uploaded_files"]
            # Call the update_conversation_files function to update the conversation in Redis
            update_response = await update_conversation_files(
                user_id=user_id,
                conversation_id=conversation_id,
                uploaded_files=uploaded_files
            )

            return {"message": "Files uploaded and conversation updated successfully.", "details": uploaded_files}
        else:
            raise HTTPException(status_code=400, detail="No files were processed successfully.")

    except HTTPException as e:
        print(f"HTTPException: {e.detail}")
        raise
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@app.get("/api/get_uploaded_files/{conversation_id}")
async def get_uploaded_files(conversation_id: str, current_user: dict = Depends(get_authenticated_user)):
    """
    Retrieve uploaded files for a specific conversation and the current authenticated user.
    """
    try:
        # Retrieve user-specific details
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User authentication failed.")

        # Define the conversation-specific directory
        user_storage_base = os.path.join(APIS, "users_storage")
        user_dir = os.path.join(user_storage_base, user_id)
        conversation_dir = os.path.join(user_dir, conversation_id)

        # Check if the directory exists
        if not os.path.exists(conversation_dir):
            return JSONResponse(content={"files": [], "message": "No files found for this conversation."}, status_code=200)

        # Retrieve all files within the conversation directory
        files = [
            file for file in os.listdir(conversation_dir) if os.path.isfile(os.path.join(conversation_dir, file))
        ]

        if not files:
            return JSONResponse(content={"files": [], "message": "No files found for this conversation."}, status_code=200)

        # Prepare a detailed response with file paths
        file_details = [
            {"file_name": file, "file_path": os.path.join(conversation_dir, file)} for file in files
        ]

        return JSONResponse(content={"files": file_details, "message": "Files retrieved successfully."}, status_code=200)

    except HTTPException as e:
        print(f"HTTPException: {e.detail}")
        raise
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


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


@app.get('/api/fetch_conversations')
async def fetch_conversations(current_user: dict = Depends(get_authenticated_user)):
    user_id = current_user.get("user_id")
    user_email = current_user.get("email")

    if not user_id or not user_email:
        raise HTTPException(status_code=400, detail="Invalid user details.")

    conversations = await fetch_user_conversations(user_id)

    if not conversations:
        return {"message": "No conversations found.", "conversations": []}

    return {"conversations": conversations}


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str,  current_user: str = Depends(get_authenticated_user)):
    user_id = current_user.get("user_id")
    return await fetch_conversation(user_id=user_id, conversation_id=conversation_id)


@app.get("/api/view_pdf/{conversation_id}/{file_name}")
async def view_pdf(conversation_id: str, file_name: str, current_user: dict = Depends(get_authenticated_user)):
    user_id = current_user.get('user_id')
    selected_file_path = os.path.join(APIS, 'users_storage', user_id, conversation_id, file_name)

    if not os.path.exists(selected_file_path):
        raise HTTPException(status_code=404, detail="File not found")

    # Use FileResponse and specify headers for inline display
    return FileResponse(
        selected_file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{file_name}"'}
    )


async def get_authenticated_user_websocket(websocket: WebSocket):
    token = websocket.cookies.get("auth_token")

    if not token:
        raise HTTPException(status_code=401, detail="Authorization token missing")

    try:
        payload = decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        exp = payload.get("exp")
        if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
            raise HTTPException(status_code=401, detail="Token has expired")

        return {
            "user_id": payload.get("user_id"),
            "email": payload.get("email"),
        }

    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.websocket("/api/llm_chat/{conversation_id}")
async def websocket_llm_chat(conversation_id: str, websocket: WebSocket, current_user: dict = Depends(get_authenticated_user_websocket)):
    user_id = current_user.get('user_id')
    config = {"configurable": {'user_id': user_id ,"conversation_id": conversation_id}}
    await websocket.accept()
    try:
        await websocket.send_text("Connected to LLM WebSocket! Start sending your queries.")

        seen_tool_calls = set()

        while True:
            user_query = await websocket.receive_text()

            query = {'messages': [HumanMessage(content=user_query)]}

            async for event in react_agent.astream(query, stream_mode='values', config=config):
                if 'messages' not in event:
                    continue

                for msg in event['messages']:
                    if isinstance(msg, HumanMessage):
                        continue

                    elif isinstance(msg, AIMessage) and not msg.content:
                        tool_calls = msg.additional_kwargs['tool_calls']

                        for tool_call in tool_calls:
                            tool_name = tool_call['function']['name']
                            args = tool_call['function']['arguments']

                            tool_call_id = (tool_name, str(args))
                            if tool_call_id not in seen_tool_calls:
                                seen_tool_calls.add(tool_call_id)
                                await websocket.send_text(f"Calling tool: {tool_name}\nTool arguments: {args}")

                    elif isinstance(msg, AIMessage):
                        if msg.content:
                            await websocket.send_text(msg.content)

    except WebSocketDisconnect:
        print("WebSocket connection closed.")
