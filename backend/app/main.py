import os
import uuid

from dotenv import load_dotenv

load_dotenv()

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, get_db
from app.models.document import Document

from app.services.document_db_service import (
    delete_document_record,
    get_all_documents,
    get_document_by_id,
)

from app.services.document_service import (
    extract_pdf_text,
    split_documents,
)

from app.services.embedding_service import (
    embed_query_with_retry,
    llm,
)

from app.services.ingestion_service import (
    ingest_chunks,
)

from app.services.qdrant_service import (
    client,
    create_collection,
    delete_document_chunks,
    search_documents,
    search_documents_mmr,
)
from app.tasks.document_tasks import process_document

app = FastAPI()


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# ROOT
# --------------------------------------------------

@app.get("/")
def root():
    return {
        "message": "RAG Document QA API is running"
    }


# --------------------------------------------------
# QDRANT HEALTH
# --------------------------------------------------

@app.get("/qdrant-health")
def qdrant_health():
    try:
        collections = client.get_collections()

        return {
            "status": "connected",
            "collections": len(
                collections.collections
            ),
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Qdrant connection failed: {str(error)}",
        )


# --------------------------------------------------
# CREATE QDRANT COLLECTION
# --------------------------------------------------

@app.post("/qdrant/create-collection")
def create_qdrant_collection():
    try:
        create_collection()

        return {
            "message": (
                "Collection created successfully"
            ),
            "collection": "document_chunks",
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# --------------------------------------------------
# DEBUG SEARCH
# --------------------------------------------------

@app.get("/documents/search")
def search_documents_endpoint(
    query: str,
):
    query_vector = embed_query_with_retry(
    query
)

    results = search_documents(
        query_vector=query_vector,
        limit=3,
    )

    return {
        "query": query,
        "results": [
            {
                "score": point.score,
                "text": point.payload.get(
                    "text",
                    "",
                ),
            }
            for point in results
        ],
    }


# --------------------------------------------------
# RESPONSE TEXT EXTRACTION
# --------------------------------------------------

def extract_answer_content(content):
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts = []

        for item in content:
            if isinstance(item, str):
                text_parts.append(item)

            elif isinstance(item, dict):
                if item.get("text"):
                    text_parts.append(
                        str(item.get("text"))
                    )

        return "".join(
            text_parts
        ).strip()

    return str(content).strip()


# --------------------------------------------------
# CHAT
# --------------------------------------------------

@app.get("/chat")
def chat(
    query: str,
    document_id: str,
):
    # ----------------------------------------------
    # 1. Convert question into embedding
    # ----------------------------------------------

    query_vector = embed_query_with_retry(
    query
)

    # ----------------------------------------------
    # 2. Search only selected document
    # ----------------------------------------------

    results = search_documents_mmr(
        query_vector=query_vector,
        limit=6,
        fetch_limit=20,
        lambda_mult=0.75,
        document_id=document_id,
    )

    # ----------------------------------------------
    # 3. Remove weak results
    # ----------------------------------------------

    SCORE_THRESHOLD = 0.50

    results = [
        point
        for point in results
        if point.score >= SCORE_THRESHOLD
    ]

    # ----------------------------------------------
    # 4. Handle no relevant results
    # ----------------------------------------------

    if not results:
        return {
            "question": query,
            "document_id": document_id,
            "answer": (
                "I don't know based on the provided "
                "documents."
            ),
            "sources": [],
        }

    # ----------------------------------------------
    # 5. Build context
    #
    # Supports both:
    #
    # - parent-child chunking
    # - normal chunks
    #
    # Your current Qdrant data may not contain
    # parent_id / parent_text, so we fall back
    # to the normal chunk text.
    # ----------------------------------------------

    context_sections = []

    seen_texts = set()

    for index, point in enumerate(
        results,
        start=1,
    ):
        text = point.payload.get(
            "parent_text"
        )

        if not text:
            text = point.payload.get(
                "text",
                "",
            )

        if not text:
            continue

        normalized_text = (
            text.strip().lower()
        )

        # Avoid duplicate context
        if normalized_text in seen_texts:
            continue

        seen_texts.add(
            normalized_text
        )

        filename = point.payload.get(
            "filename",
            "Unknown document",
        )

        page = point.payload.get(
            "page",
            0,
        )

        context_sections.append(
            f"""
--- SOURCE {index} ---
Document: {filename}
Page: {page}

{text}
""".strip()
        )

    context = "\n\n".join(
        context_sections
    )

    # Final safety fallback
    if not context.strip():
        return {
            "question": query,
            "document_id": document_id,
            "answer": (
                "I don't know based on the provided "
                "documents."
            ),
            "sources": [],
        }

    # ----------------------------------------------
    # 6. Generalized RAG prompt
    # ----------------------------------------------

    prompt = f"""
You are a helpful document question-answering assistant.

Answer the user's question using ONLY the provided document context.

IMPORTANT RULES:

1. The document context may contain direct answers, lists, tables,
   headings, bullet points, or information spread across multiple
   retrieved sources.

2. If the answer is explicitly present in the context, answer it
   directly. Do NOT say that you don't know when the requested
   information is clearly present.

3. Combine information from multiple retrieved sources when doing so
   helps answer the user's question and the sources are clearly relevant.

4. Keep distinct topics, entities, projects, people, or sections
   separate unless the context clearly establishes a relationship
   between them.

5. Do not infer relationships merely because pieces of information
   appear close together in the retrieved text.

6. Do not invent information, add unsupported details, or use outside
   knowledge.

7. If the answer is not supported anywhere in the provided document
   context, say exactly:

"I don't know based on the provided documents."

Answer clearly and concisely.

DOCUMENT CONTEXT:
{context}

USER QUESTION:
{query}
"""

    # ----------------------------------------------
    # 7. Generate answer
    # ----------------------------------------------

    try:
        response = llm.invoke(
            prompt
        )

        answer = extract_answer_content(
            response.content
        )

        if not answer:
            answer = (
                "I don't know based on the provided "
                "documents."
            )

    except HTTPException:
        raise

    except Exception as error:
        error_message = str(error)

        print(
            "LLM error:",
            error_message,
        )

        if (
            "429" in error_message
            or "RESOURCE_EXHAUSTED"
            in error_message
            or "RateLimitError"
            in error_message
            or "quota"
            in error_message.lower()
        ):
            raise HTTPException(
                status_code=429,
                detail=(
                    "The AI request limit has been "
                    "reached. Please wait and try "
                    "again later."
                ),
            )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to generate an AI response."
            ),
        )

    # ----------------------------------------------
    # 8. Return answer and sources
    # ----------------------------------------------

    return {
        "question": query,
        "document_id": document_id,
        "answer": answer,
        "sources": [
            {
                "score": point.score,
                "text": point.payload.get(
                    "parent_text",
                    point.payload.get(
                        "text",
                        "",
                    ),
                ),
                "filename": point.payload.get(
                    "filename",
                    "Unknown document",
                ),
                "page": point.payload.get(
                    "page",
                    0,
                ),
            }
            for point in results
        ],
    }

# --------------------------------------------------
# UPLOAD DOCUMENT
# --------------------------------------------------

@app.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # Validate PDF
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed.",
        )

    document_id = str(uuid.uuid4())

    filename = file.filename or "document.pdf"

    # Create uploads directory
    os.makedirs(
        "uploads",
        exist_ok=True,
    )

    file_path = os.path.join(
        "uploads",
        f"{document_id}.pdf",
    )

    # Save uploaded file
    with open(file_path, "wb") as buffer:
        buffer.write(
            await file.read()
        )

    # Create database record
    document = Document(
        id=document_id,
        filename=filename,
        file_path=file_path,
        status="processing",
        pages=0,
        chunks=0,
    )

    db.add(document)
    db.commit()

    # Send processing to Celery
    task = process_document.delay(
        file_path=file_path,
        document_id=document_id,
        filename=filename,
    )

    return {
        "message": (
            "PDF uploaded successfully. "
            "Processing started."
        ),
        "document_id": document_id,
        "filename": filename,
        "task_id": task.id,
        "status": "processing",
    }


# --------------------------------------------------
# GET ALL DOCUMENTS
# --------------------------------------------------

@app.get("/documents")
def get_documents(
    db: Session = Depends(get_db),
):
    documents = get_all_documents(
        db
    )

    return {
        "documents": [
            {
                "id": str(document.id),
                "filename": document.filename,
                "file_path": (
                    document.file_path
                ),
                "status": document.status,
                "pages": document.pages,
                "chunks": document.chunks,
                "created_at": (
                    document.created_at
                ),
            }
            for document in documents
        ]
    }


# --------------------------------------------------
# GET SINGLE DOCUMENT
# --------------------------------------------------

@app.get("/documents/{document_id}")
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
):
    document = get_document_by_id(
        db=db,
        document_id=document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    return {
        "id": str(document.id),
        "filename": document.filename,
        "status": document.status,
        "pages": document.pages,
        "chunks": document.chunks,
        "created_at": document.created_at,
    }


# --------------------------------------------------
# DELETE DOCUMENT
# --------------------------------------------------

@app.delete("/documents/{document_id}")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
):
    # 1. Find document
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id
        )
        .first()
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    file_path = document.file_path

    try:
        # 2. Delete Qdrant vectors
        delete_document_chunks(
            document_id
        )

        # 3. Delete PostgreSQL record
        delete_document_record(
            db=db,
            document_id=document_id,
        )

        # 4. Delete physical PDF
        if (
            file_path
            and os.path.exists(
                file_path
            )
        ):
            os.remove(
                file_path
            )

        return {
            "message": (
                "Document deleted successfully"
            ),
            "document_id": document_id,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )