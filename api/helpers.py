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


async def process_pdfs(files, client_, collection_name):
    uploaded_files_info = {}
    
    for file in files:
        # Save the file to the specified directory
        file_path = os.path.join(upload_directory, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())
        
        # Extract text from the PDF
        pdf_text = extract_text_from_pdf(file_path)
        
        # Split the text into manageable chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        text_chunks = text_splitter.split_text(pdf_text)
        
        # Generate embeddings for each text chunk
        embeddings_model = GoogleGenerativeAIEmbeddings(model='models/text-embedding-004')
        embeddings = embeddings_model.embed_documents(text_chunks)

        # Store embeddings in Qdrant
        pdf_id = file.filename
        points = [
            models.PointStruct(
                id=i,
                payload={"pdf_id": pdf_id},
                vector=embedding # Convert to list if needed
            )
            for i, embedding in enumerate(embeddings)
        ]
        
        # Upsert points into Qdrant and capture the response
        upsert_response = client_.upsert(collection_name=collection_name, points=points)

        # Store the result in a dictionary
        uploaded_files_info[file.filename] = {
            "total_chunks": len(text_chunks),
            "upsert_response": upsert_response
        }

    return uploaded_files_info

def extract_text_from_pdf(file_path) -> str:
    # Use PyMuPDF to extract text from PDF
    pdf_document = fitz.open(file_path)
    text = ""
    for page in pdf_document:
        text += page.get_text()
    pdf_document.close()
    return text