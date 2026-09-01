from app.core.celery_app import celery_app
from app.db.database import SessionLocal
from app.models.document import Document

from app.services.document_service import (
    extract_pdf_text,
    split_documents,
)

from app.services.ingestion_service import (
    ingest_chunks,
)


@celery_app.task(
    bind=True,
    name="app.tasks.document_tasks.process_document",
)
def process_document(
    self,
    file_path: str,
    document_id: str,
    filename: str,
):
    """
    Background task for processing an uploaded PDF.
    """

    db = SessionLocal()

    try:
        # -----------------------------
        # Step 1: Mark as processing
        # -----------------------------
        document = (
            db.query(Document)
            .filter(
                Document.id == document_id
            )
            .first()
        )

        if document is None:
            raise Exception(
                f"Document {document_id} not found"
            )

        document.status = "processing"
        db.commit()

        self.update_state(
            state="PROCESSING",
            meta={
                "step": "extracting",
                "progress": 20,
            },
        )

        # -----------------------------
        # Step 2: Extract PDF
        # -----------------------------
        documents = extract_pdf_text(
            file_path
        )

        page_count = len(documents)

        # -----------------------------
        # Step 3: Split into chunks
        # -----------------------------
        self.update_state(
            state="PROCESSING",
            meta={
                "step": "chunking",
                "progress": 40,
            },
        )

        chunks = split_documents(
            documents
        )

        # -----------------------------
        # Step 4: Generate embeddings
        # and store in Qdrant
        # -----------------------------
        self.update_state(
            state="PROCESSING",
            meta={
                "step": "embedding",
                "progress": 60,
            },
        )

        inserted_chunks = ingest_chunks(
            chunks=chunks,
            document_id=document_id,
            filename=filename,
        )

        # -----------------------------
        # Step 5: Update DB
        # -----------------------------
        document = (
            db.query(Document)
            .filter(
                Document.id == document_id
            )
            .first()
        )

        if document:
            document.status = "completed"
            document.pages = page_count
            document.chunks = inserted_chunks

            db.commit()

        # -----------------------------
        # Task completed
        # -----------------------------
        return {
            "status": "completed",
            "document_id": document_id,
            "filename": filename,
            "pages": page_count,
            "chunks": inserted_chunks,
        }

    except Exception as error:

        print(
            f"Document processing failed: {error}"
        )

        # -----------------------------
        # Mark document as failed
        # -----------------------------
        try:
            db.rollback()

            document = (
                db.query(Document)
                .filter(
                    Document.id == document_id
                )
                .first()
            )

            if document:
                document.status = "failed"
                db.commit()

        except Exception as db_error:
            print(
                f"Failed to update document status: "
                f"{db_error}"
            )

            db.rollback()

        # Tell Celery that the task failed
        raise

    finally:
        db.close()