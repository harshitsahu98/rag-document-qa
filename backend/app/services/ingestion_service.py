import time
import uuid

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.embedding_service import (
    embed_documents_with_retry,
)
from app.services.qdrant_service import insert_documents_batch


# -----------------------------
# CHUNK CONFIGURATION
# -----------------------------

PARENT_CHUNK_SIZE = 3500
PARENT_CHUNK_OVERLAP = 300

CHILD_CHUNK_SIZE = 900
CHILD_CHUNK_OVERLAP = 150

# Number of chunks embedded together
EMBEDDING_BATCH_SIZE = 20

# Number of vectors inserted into Qdrant together
QDRANT_BATCH_SIZE = 20


def create_parent_child_chunks(documents):
    """
    Create large parent chunks first.

    Each parent chunk is then divided into smaller
    child chunks.

    Child chunks are embedded and searched, while
    parent chunks are stored in the payload for
    providing better context to the LLM.
    """

    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=PARENT_CHUNK_SIZE,
        chunk_overlap=PARENT_CHUNK_OVERLAP,
        separators=[
            "\n\n",
            "\n",
            ". ",
            " ",
            "",
        ],
    )

    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHILD_CHUNK_SIZE,
        chunk_overlap=CHILD_CHUNK_OVERLAP,
        separators=[
            "\n\n",
            "\n",
            ". ",
            " ",
            "",
        ],
    )

    parent_chunks = parent_splitter.split_documents(
        documents
    )

    child_chunks = []

    for parent_index, parent_chunk in enumerate(
        parent_chunks
    ):

        parent_id = str(uuid.uuid4())

        parent_text = (
            parent_chunk.page_content
        )

        children = child_splitter.split_documents(
            [parent_chunk]
        )

        for child_index, child_chunk in enumerate(
            children
        ):

            child_chunks.append(
                {
                    # Parent information
                    "parent_id": parent_id,
                    "parent_index": parent_index,
                    "parent_text": parent_text,
                    "parent_metadata": (
                        parent_chunk.metadata
                    ),

                    # Child information
                    "child_index": child_index,
                    "child_text": (
                        child_chunk.page_content
                    ),
                }
            )

    return child_chunks


def ingest_chunks(
    chunks,
    document_id: str,
    filename: str,
):
    """
    Complete ingestion pipeline.

    1. Create parent-child chunks.
    2. Embed child chunks in batches.
    3. Store vectors in Qdrant in batches.
    """

    parent_child_chunks = (
        create_parent_child_chunks(chunks)
    )

    if not parent_child_chunks:
        return 0

    total_chunks = len(parent_child_chunks)

    print(
        f"Starting ingestion of "
        f"{total_chunks} child chunks"
    )

    inserted = 0

    for batch_start in range(
        0,
        total_chunks,
        EMBEDDING_BATCH_SIZE,
    ):

        batch = parent_child_chunks[
            batch_start:
            batch_start + EMBEDDING_BATCH_SIZE
        ]

        batch_end = (
            batch_start + len(batch)
        )

        print(
            f"Embedding chunks "
            f"{batch_start + 1}-"
            f"{batch_end} "
            f"of {total_chunks}"
        )

        # ---------------------------------
        # Extract child texts
        # ---------------------------------

        texts = [
            item["child_text"]
            for item in batch
        ]

        # ---------------------------------
        # Generate embeddings
        #
        # This function should handle
        # retry + exponential backoff.
        # ---------------------------------

        vectors = embed_documents_with_retry(
            texts
        )

        if len(vectors) != len(batch):
            raise Exception(
                "Number of generated vectors "
                "does not match number of chunks"
            )

        # ---------------------------------
        # Prepare Qdrant points
        # ---------------------------------

        points = []

        for item, vector in zip(
            batch,
            vectors,
        ):

            point_id = str(
                uuid.uuid4()
            )

            metadata = {
                "document_id": document_id,
                "filename": filename,

                # Parent information
                "parent_id": (
                    item["parent_id"]
                ),
                "parent_index": (
                    item["parent_index"]
                ),
                "parent_text": (
                    item["parent_text"]
                ),

                # Child information
                "child_index": (
                    item["child_index"]
                ),

                # Source information
                "source": (
                    item["parent_metadata"]
                    .get("source")
                ),

                "page": (
                    item["parent_metadata"]
                    .get("page", 0)
                    + 1
                ),
            }

            points.append(
                {
                    "id": point_id,
                    "text": item[
                        "child_text"
                    ],
                    "vector": vector,
                    "metadata": metadata,
                }
            )

        # ---------------------------------
        # Insert all points together
        # ---------------------------------

        insert_documents_batch(
            points
        )

        inserted += len(points)

        print(
            f"Successfully inserted "
            f"{inserted}/{total_chunks} chunks"
        )

        # ---------------------------------
        # Small delay between batches
        #
        # Helps reduce Gemini rate limits.
        # ---------------------------------

        if batch_end < total_chunks:

            time.sleep(1)

    print(
        f"Document ingestion completed. "
        f"Total chunks inserted: "
        f"{inserted}"
    )

    return inserted