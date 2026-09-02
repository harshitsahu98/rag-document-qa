import time
import uuid

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
)

from qdrant_client.models import (
    PointStruct,
)

from app.services.embedding_service import (
    embed_documents_with_retry,
)

from app.services.qdrant_service import (
    insert_documents_batch,
)


# --------------------------------------------------
# CHUNK CONFIGURATION
# --------------------------------------------------

PARENT_CHUNK_SIZE = 3500
PARENT_CHUNK_OVERLAP = 300

CHILD_CHUNK_SIZE = 900
CHILD_CHUNK_OVERLAP = 150


# --------------------------------------------------
# BATCH CONFIGURATION
# --------------------------------------------------

EMBEDDING_BATCH_SIZE = 20
QDRANT_BATCH_SIZE = 20


# --------------------------------------------------
# CREATE PARENT-CHILD CHUNKS
# --------------------------------------------------

def create_parent_child_chunks(documents):
    """
    Create large parent chunks first.

    Each parent chunk is divided into smaller child chunks.

    Child chunks:
        - Used for embedding and retrieval.

    Parent chunks:
        - Stored in Qdrant payload.
        - Used as context for the LLM.
    """

    parent_splitter = (
        RecursiveCharacterTextSplitter(
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
    )

    child_splitter = (
        RecursiveCharacterTextSplitter(
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
    )

    # ----------------------------------------------
    # Create parent chunks
    # ----------------------------------------------

    parent_chunks = (
        parent_splitter.split_documents(
            documents
        )
    )

    child_chunks = []

    # ----------------------------------------------
    # Create children for every parent
    # ----------------------------------------------

    for parent_index, parent_chunk in enumerate(
        parent_chunks
    ):

        parent_id = str(
            uuid.uuid4()
        )

        parent_text = (
            parent_chunk.page_content
        )

        children = (
            child_splitter.split_documents(
                [parent_chunk]
            )
        )

        for child_index, child_chunk in enumerate(
            children
        ):

            child_chunks.append(
                {
                    # ----------------------------------
                    # Parent data
                    # ----------------------------------

                    "parent_id": parent_id,

                    "parent_index": (
                        parent_index
                    ),

                    "parent_text": (
                        parent_text
                    ),

                    "parent_metadata": (
                        parent_chunk.metadata
                    ),

                    # ----------------------------------
                    # Child data
                    # ----------------------------------

                    "child_index": (
                        child_index
                    ),

                    "child_text": (
                        child_chunk.page_content
                    ),
                }
            )

    return child_chunks


# --------------------------------------------------
# INGEST CHUNKS
# --------------------------------------------------

def ingest_chunks(
    chunks,
    document_id: str,
    filename: str,
):
    """
    Complete ingestion pipeline.

    1. Create parent-child chunks.
    2. Generate embeddings for child chunks.
    3. Store vectors in Qdrant.

    IMPORTANT:

    Qdrant payload fields are stored directly at the
    top level.

    Example:

    {
        "text": "...",
        "document_id": "...",
        "filename": "...",
        "parent_text": "..."
    }

    This allows filtering with:

    key="document_id"
    """

    # ----------------------------------------------
    # Create parent-child chunks
    # ----------------------------------------------

    parent_child_chunks = (
        create_parent_child_chunks(
            chunks
        )
    )

    if not parent_child_chunks:
        return 0

    total_chunks = len(
        parent_child_chunks
    )

    print(
        f"Starting ingestion of "
        f"{total_chunks} child chunks"
    )

    inserted = 0

    # ----------------------------------------------
    # Process embeddings in batches
    # ----------------------------------------------

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
            batch_start
            + len(batch)
        )

        print(
            f"Embedding chunks "
            f"{batch_start + 1}-"
            f"{batch_end} "
            f"of {total_chunks}"
        )

        # ------------------------------------------
        # Extract child texts
        # ------------------------------------------

        texts = [
            item["child_text"]
            for item in batch
        ]

        # ------------------------------------------
        # Generate embeddings
        # ------------------------------------------

        vectors = (
            embed_documents_with_retry(
                texts
            )
        )

        if (
            len(vectors)
            != len(batch)
        ):
            raise Exception(
                "Number of generated vectors "
                "does not match number of chunks"
            )

        # ------------------------------------------
        # Create Qdrant points
        # ------------------------------------------

        points = []

        for item, vector in zip(
            batch,
            vectors,
        ):

            point_id = str(
                uuid.uuid4()
            )

            # --------------------------------------
            # IMPORTANT:
            #
            # document_id MUST be at the top level
            # because Qdrant filters using:
            #
            # key="document_id"
            #
            # NOT:
            #
            # key="metadata.document_id"
            # --------------------------------------

            payload = {

                # ----------------------------------
                # Child chunk
                # ----------------------------------

                "text": (
                    item["child_text"]
                ),

                # ----------------------------------
                # Document identification
                # ----------------------------------

                "document_id": (
                    document_id
                ),

                "filename": (
                    filename
                ),

                # ----------------------------------
                # Parent chunk
                # ----------------------------------

                "parent_id": (
                    item["parent_id"]
                ),

                "parent_index": (
                    item["parent_index"]
                ),

                "parent_text": (
                    item["parent_text"]
                ),

                # ----------------------------------
                # Child information
                # ----------------------------------

                "child_index": (
                    item["child_index"]
                ),

                # ----------------------------------
                # Source metadata
                # ----------------------------------

                "source": (
                    item[
                        "parent_metadata"
                    ].get(
                        "source",
                        filename,
                    )
                ),

                "page": (
                    item[
                        "parent_metadata"
                    ].get(
                        "page",
                        0,
                    )
                    + 1
                ),
            }

            # --------------------------------------
            # Create PointStruct
            # --------------------------------------

            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        # ------------------------------------------
        # Insert vectors into Qdrant
        # ------------------------------------------

        insert_documents_batch(
            points
        )

        inserted += len(
            points
        )

        print(
            f"Successfully inserted "
            f"{inserted}/"
            f"{total_chunks} chunks"
        )

        # ------------------------------------------
        # Delay between batches
        # ------------------------------------------

        if batch_end < total_chunks:

            time.sleep(1)

    print(
        f"Document ingestion completed. "
        f"Total chunks inserted: "
        f"{inserted}"
    )

    return inserted
