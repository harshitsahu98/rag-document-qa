import uuid

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)

from fastapi.middleware.cors import (
    CORSMiddleware,
)

from sqlalchemy.orm import Session

from app.db.database import (
    Base,
    engine,
    get_db,
)

from app.models.document import (
    Document,
)

from app.services.document_db_service import (
    delete_document_record,
    get_all_documents,
    get_document_by_id,
)

from app.services.embedding_service import (
    embed_query_with_retry,
    llm,
)

from app.services.qdrant_service import (
    client,
    create_collection,
    delete_document_chunks,
    search_documents,
    search_documents_mmr,
)

from app.services.supabase_service import (
    supabase,
)

from app.tasks.document_tasks import (
    process_document,
)


# --------------------------------------------------
# APP
# --------------------------------------------------

app = FastAPI()


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

@app.on_event("startup")
def create_database_tables():
    Base.metadata.create_all(
        bind=engine
    )

    create_collection()


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://rag-document-qa-three.vercel.app",
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
            detail=(
                "Qdrant connection failed: "
                f"{str(error)}"
            ),
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
# RESPONSE TEXT EXTRACTION
# --------------------------------------------------

def extract_answer_content(content):
    if content is None:
        return ""

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts = []

        for item in content:

            if isinstance(item, str):
                text_parts.append(item)

            elif isinstance(item, dict):
                text = item.get("text")

                if text:
                    text_parts.append(
                        str(text)
                    )

        return "".join(
            text_parts
        ).strip()

    return str(
        content
    ).strip()


# --------------------------------------------------
# DEBUG SEARCH
# --------------------------------------------------

@app.get("/documents/search")
def search_documents_endpoint(
    query: str,
    document_id: str | None = None,
):
    query_vector = embed_query_with_retry(
        query
    )

    results = search_documents(
        query_vector=query_vector,
        limit=10,
        document_id=document_id,
    )

    return {
        "query": query,
        "document_id": document_id,
        "number_of_results": len(
            results
        ),
        "results": [
            {
                "id": str(
                    point.id
                ),
                "score": point.score,
                "text": point.payload.get(
                    "text",
                    "",
                ),
                "payload": point.payload,
            }
            for point in results
        ],
    }


# --------------------------------------------------
# CHAT
# --------------------------------------------------

@app.get("/chat")
def chat(
    query: str,
    document_id: str,
):
    query_vector = embed_query_with_retry(
        query
    )

    results = search_documents_mmr(
        query_vector=query_vector,
        limit=6,
        fetch_limit=20,
        lambda_mult=0.75,
        document_id=document_id,
    )

    print(
        "\n========== RAG DEBUG =========="
    )

    print(
        "QUESTION:",
        query
    )

    print(
        "DOCUMENT ID:",
        document_id
    )

    print(
        "RESULT COUNT:",
        len(results)
    )

    for index, point in enumerate(
        results,
        start=1,
    ):
        print(
            f"\nRESULT {index}"
        )

        print(
            "Score:",
            point.score
        )

        print(
            "Point document_id:",
            point.payload.get(
                "document_id"
            )
        )

        print(
            "Text:",
            point.payload.get(
                "text",
                "",
            )[:300]
        )

    print(
        "\n================================\n"
    )

    # --------------------------------------------------
    # NO RESULTS
    # --------------------------------------------------

    if not results:
        return {
            "question": query,
            "document_id": document_id,
            "answer": (
                "I don't know based on the "
                "provided documents."
            ),
            "sources": [],
        }

    # --------------------------------------------------
    # BUILD CONTEXT
    # --------------------------------------------------

    context_sections = []

    seen_texts = set()

    for index, point in enumerate(
        results,
        start=1,
    ):
        text = (
            point.payload.get(
                "parent_text"
            )
            or point.payload.get(
                "text",
                "",
            )
        )

        if not text:
            continue

        normalized_text = (
            text
            .strip()
            .lower()
        )

        if (
            normalized_text
            in seen_texts
        ):
            continue

        seen_texts.add(
            normalized_text
        )

        filename = (
            point.payload.get(
                "filename"
            )
            or point.payload.get(
                "source"
            )
            or "Unknown document"
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

    # --------------------------------------------------
    # EMPTY CONTEXT
    # --------------------------------------------------

    if not context.strip():
        return {
            "question": query,
            "document_id": document_id,
            "answer": (
                "I don't know based on the "
                "provided documents."
            ),
            "sources": [],
        }

    # --------------------------------------------------
    # PROMPT
    # --------------------------------------------------

    prompt = f"""
You are a helpful document question-answering assistant.

Answer the user's question using ONLY the document
context below.

RULES:

1. Answer the question directly when the information
is present in the document context.

2. The answer may be spread across multiple chunks.
Combine those chunks when appropriate.

3. Headings, bullet points, tables, and sections are
all valid sources of information.

4. Do not use outside knowledge.

5. Do not invent information.

6. Only say the following sentence when the answer
cannot be found in the provided context:

"I don't know based on the provided documents."

DOCUMENT CONTEXT:

{context}

USER QUESTION:

{query}

ANSWER:
"""

    # --------------------------------------------------
    # GENERATE ANSWER
    # --------------------------------------------------

    try:
        response = llm.invoke(
            prompt
        )

        answer = extract_answer_content(
            response.content
        )

        if not answer:
            answer = (
                "I don't know based on the "
                "provided documents."
            )

    except Exception as error:

        error_message = str(
            error
        )

        print(
            "LLM ERROR:",
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
                "Failed to generate an AI "
                "response."
            ),
        )

    # --------------------------------------------------
    # RETURN RESPONSE
    # --------------------------------------------------

    return {
        "question": query,
        "document_id": document_id,
        "answer": answer,
        "sources": [
            {
                "id": str(
                    point.id
                ),
                "score": point.score,
                "text": (
                    point.payload.get(
                        "parent_text"
                    )
                    or point.payload.get(
                        "text",
                        "",
                    )
                ),
                "filename": (
                    point.payload.get(
                        "filename"
                    )
                    or point.payload.get(
                        "source"
                    )
                    or "Unknown document"
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
    db: Session = Depends(
        get_db
    ),
):
    if (
        file.content_type
        != "application/pdf"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Only PDF files are allowed."
            ),
        )

    document_id = str(
        uuid.uuid4()
    )

    filename = (
        file.filename
        or "document.pdf"
    )

    storage_path = (
        f"{document_id}/{filename}"
    )

    try:
        file_content = await file.read()

        supabase.storage.from_(
            "documents"
        ).upload(
            path=storage_path,
            file=file_content,
            file_options={
                "content-type":
                "application/pdf",
            },
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to upload PDF: "
                f"{str(error)}"
            ),
        )

    try:
        document = Document(
            id=document_id,
            filename=filename,
            file_path=storage_path,
            status="processing",
            pages=0,
            chunks=0,
        )

        db.add(
            document
        )

        db.commit()

        db.refresh(
            document
        )

        task = process_document.delay(
            storage_path=storage_path,
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
            "storage_path": storage_path,
            "task_id": task.id,
            "status": "processing",
        }

    except Exception as error:

        db.rollback()

        try:
            supabase.storage.from_(
                "documents"
            ).remove(
                [storage_path]
            )

        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to start document "
                f"processing: {str(error)}"
            ),
        )


# --------------------------------------------------
# GET ALL DOCUMENTS
# --------------------------------------------------

@app.get("/documents")
def get_documents(
    db: Session = Depends(
        get_db
    ),
):
    documents = get_all_documents(
        db
    )

    return {
        "documents": [
            {
                "id": str(
                    document.id
                ),
                "filename": (
                    document.filename
                ),
                "file_path": (
                    document.file_path
                ),
                "status": (
                    document.status
                ),
                "pages": (
                    document.pages
                ),
                "chunks": (
                    document.chunks
                ),
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

@app.get(
    "/documents/{document_id}"
)
def get_document(
    document_id: str,
    db: Session = Depends(
        get_db
    ),
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
        "id": str(
            document.id
        ),
        "filename": (
            document.filename
        ),
        "file_path": (
            document.file_path
        ),
        "status": (
            document.status
        ),
        "pages": (
            document.pages
        ),
        "chunks": (
            document.chunks
        ),
        "created_at": (
            document.created_at
        ),
    }


# --------------------------------------------------
# DELETE DOCUMENT
# --------------------------------------------------

@app.delete(
    "/documents/{document_id}"
)
def delete_document(
    document_id: str,
    db: Session = Depends(
        get_db
    ),
):
    document = (
        db.query(Document)
        .filter(
            Document.id
            == document_id
        )
        .first()
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    storage_path = (
        document.file_path
    )

    try:
        delete_document_chunks(
            document_id
        )

        if storage_path:
            supabase.storage.from_(
                "documents"
            ).remove(
                [storage_path]
            )

        delete_document_record(
            db=db,
            document_id=document_id,
        )

        return {
            "message": (
                "Document deleted successfully"
            ),
            "document_id": document_id,
        }

    except Exception as error:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(
                error
            ),
        )


# --------------------------------------------------
# DEBUG QDRANT
# --------------------------------------------------

@app.get("/debug/qdrant")
def debug_qdrant():
    points, _ = client.scroll(
        collection_name="document_chunks",
        limit=100,
        with_payload=True,
        with_vectors=False,
    )

    return {
        "number_of_points": len(
            points
        ),
        "points": [
            {
                "id": str(
                    point.id
                ),
                "document_id": (
                    point.payload.get(
                        "document_id"
                    )
                ),
                "text": (
                    point.payload.get(
                        "text",
                        ""
                    )[:500]
                ),
                "filename": (
                    point.payload.get(
                        "filename"
                    )
                ),
                "source": (
                    point.payload.get(
                        "source"
                    )
                ),
                "page": (
                    point.payload.get(
                        "page"
                    )
                ),
                "chunk_index": (
                    point.payload.get(
                        "chunk_index"
                    )
                ),
            }
            for point in points
        ],
    }


@app.get("/debug/document-points")
def debug_document_points(
    document_id: str,
):
    from qdrant_client.models import (
        Filter,
        FieldCondition,
        MatchValue,
    )

    points, _ = client.scroll(
        collection_name="document_chunks",
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="document_id",
                    match=MatchValue(
                        value=document_id
                    ),
                )
            ]
        ),
        limit=100,
        with_payload=True,
        with_vectors=False,
    )

    return {
        "document_id": document_id,
        "number_of_points": len(points),
        "points": [
            {
                "id": str(point.id),
                "payload": point.payload,
            }
            for point in points
        ],
    }