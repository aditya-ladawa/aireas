import os
from fastapi import UploadFile
import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Directory to save uploaded files
upload_directory = "api/static/files"
os.makedirs(upload_directory, exist_ok=True)


from uuid import uuid4

async def process_pdfs(files, client_, collection_name, emb_model):
    uploaded_files_info = {}
    
    for file in files:
        # Save the uploaded PDF file
        file_path = os.path.join(upload_directory, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())
        
        # Extract text from the PDF
        pdf_text = extract_text_from_pdf(file_path)
        
        # Split the text into chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=300)
        text_chunks = text_splitter.split_text(pdf_text)
        
        # Generate embeddings for the text chunks
        embeddings = emb_model.embed_documents(text_chunks)

        pdf_id = file.filename
        points = [
            models.PointStruct(
                id=str(uuid4()),  # Ensure unique ID by combining file name and index
                payload={
                    "pdf_id": pdf_id,
                    "text": text_chunks[i]  # Store the text chunk
                },
                vector=embedding  # Convert to list if needed
            )
            for i, embedding in enumerate(embeddings)
        ]
        
        # Upsert points into Qdrant collection
        upsert_response = client_.upsert(collection_name=collection_name, points=points)

        uploaded_files_info[file.filename] = {
            "file_name": file.filename,
            "total_chunks": len(text_chunks),
            "upsert_response": upsert_response
        }

    return uploaded_files_info



def extract_text_from_pdf(file_path) -> str:
    pdf_document = fitz.open(file_path)
    text = ""
    for page in pdf_document:
        text += page.get_text()
    pdf_document.close()
    return text