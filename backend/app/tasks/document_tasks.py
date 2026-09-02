import os
import tempfile

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

from app.services.supabase_service import supabase


@celery_app.task(
    bind=True,
    name="app.tasks.document_tasks.process_document",
)
def process_document(
    self,
    storage_path: str,
    document_id: str,
    filename: str,
):
    """
    Background task for processing an uploaded PDF.

    The PDF is:
    1. Downloaded from Supabase Storage
    2. Temporarily saved locally
    3. Extracted and chunked
    4. Embedded and stored in Qdrant
    5. Local temporary file is deleted
    """

    db = SessionLocal()

    temp_file_path = None

    try:
        # --------------------------------------------
        # Step 1: Mark document as processing
        # --------------------------------------------

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
                "step": "downloading",
                "progress": 10,
            },
        )

        # --------------------------------------------
        # Step 2: Download PDF from Supabase
        # --------------------------------------------

        print(
            f"Downloading {storage_path} "
            f"from Supabase..."
        )

        pdf_bytes = (
            supabase.storage
            .from_("documents")
            .download(storage_path)
        )

        # --------------------------------------------
        # Step 3: Create temporary PDF file
        # --------------------------------------------

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".pdf",
        ) as temp_file:

            temp_file.write(
                pdf_bytes
            )

            temp_file_path = (
                temp_file.name
            )

        print(
            f"Temporary PDF created: "
            f"{temp_file_path}"
        )

        # --------------------------------------------
        # Step 4: Extract PDF text
        # --------------------------------------------

        self.update_state(
            state="PROCESSING",
            meta={
                "step": "extracting",
                "progress": 25,
            },
        )

        documents = extract_pdf_text(
            temp_file_path
        )

        page_count = len(
            documents
        )

        # --------------------------------------------
        # Step 5: Split document
        # --------------------------------------------

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

        # --------------------------------------------
        # Step 6: Generate embeddings
        # and store in Qdrant
        # --------------------------------------------

        self.update_state(
            state="PROCESSING",
            meta={
                "step": "embedding",
                "progress": 60,
            },
        )

        inserted_chunks = (
            ingest_chunks(
                chunks=chunks,
                document_id=document_id,
                filename=filename,
            )
        )

        # --------------------------------------------
        # Step 7: Update database
        # --------------------------------------------

        document = (
            db.query(Document)
            .filter(
                Document.id == document_id
            )
            .first()
        )

        if document:
            document.status = (
                "completed"
            )

            document.pages = (
                page_count
            )

            document.chunks = (
                inserted_chunks
            )

            db.commit()

        # --------------------------------------------
        # Task completed
        # --------------------------------------------

        return {
            "status": "completed",
            "document_id": document_id,
            "filename": filename,
            "pages": page_count,
            "chunks": inserted_chunks,
        }

    except Exception as error:

        print(
            f"Document processing failed: "
            f"{error}"
        )

        # --------------------------------------------
        # Mark document as failed
        # --------------------------------------------

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
                document.status = (
                    "failed"
                )

                db.commit()

        except Exception as db_error:

            print(
                f"Failed to update document "
                f"status: {db_error}"
            )

            db.rollback()

        raise

    finally:

        # --------------------------------------------
        # Delete temporary PDF
        # --------------------------------------------

        if (
            temp_file_path
            and os.path.exists(
                temp_file_path
            )
        ):
            try:
                os.remove(
                    temp_file_path
                )

                print(
                    "Temporary PDF deleted"
                )

            except Exception as cleanup_error:

                print(
                    f"Failed to delete temporary "
                    f"PDF: {cleanup_error}"
                )

        db.close()