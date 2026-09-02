from qdrant_client import QdrantClient

from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    FilterSelector,
)

import numpy as np

from app.core.config import (
    QDRANT_URL,
    QDRANT_API_KEY,
)


# --------------------------------------------------
# QDRANT CLIENT
# --------------------------------------------------

if QDRANT_API_KEY:
    client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
    )
else:
    client = QdrantClient(
        url=QDRANT_URL,
    )


# --------------------------------------------------
# CONFIG
# --------------------------------------------------

COLLECTION_NAME = "document_chunks"
VECTOR_SIZE = 3072


# --------------------------------------------------
# CREATE COLLECTION
# --------------------------------------------------

def create_collection():
    if client.collection_exists(
        COLLECTION_NAME
    ):
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE,
        ),
    )


# --------------------------------------------------
# INSERT SINGLE DOCUMENT CHUNK
# --------------------------------------------------

def insert_document(
    point_id: str,
    text: str,
    vector: list[float],
    metadata: dict | None = None,
):
    payload = {
        "text": text,
    }

    if metadata:
        payload.update(
            metadata
        )

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=point_id,
                vector=vector,
                payload=payload,
            )
        ],
        wait=True,
    )


# --------------------------------------------------
# INSERT DOCUMENTS IN BATCH
# --------------------------------------------------

def insert_documents_batch(
    points: list[PointStruct],
):
    if not points:
        return

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
        wait=True,
    )


# --------------------------------------------------
# DOCUMENT FILTER
# --------------------------------------------------

def get_document_filter(
    document_id: str | None = None,
):
    if not document_id:
        return None

    return Filter(
        must=[
            FieldCondition(
                key="document_id",
                match=MatchValue(
                    value=str(document_id)
                ),
            )
        ]
    )


# --------------------------------------------------
# NORMAL SEARCH
# --------------------------------------------------

def search_documents(
    query_vector: list[float],
    limit: int = 3,
    document_id: str | None = None,
):
    query_filter = get_document_filter(
        document_id
    )

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )

    return results.points


# --------------------------------------------------
# COSINE SIMILARITY
# --------------------------------------------------

def cosine_similarity(
    vector_a,
    vector_b,
):
    vector_a = np.array(
        vector_a,
        dtype=np.float32,
    )

    vector_b = np.array(
        vector_b,
        dtype=np.float32,
    )

    denominator = (
        np.linalg.norm(vector_a)
        * np.linalg.norm(vector_b)
    )

    if denominator == 0:
        return 0.0

    return float(
        np.dot(
            vector_a,
            vector_b,
        )
        / denominator
    )


# --------------------------------------------------
# MMR SEARCH
# --------------------------------------------------

def search_documents_mmr(
    query_vector: list[float],
    limit: int = 6,
    fetch_limit: int = 20,
    lambda_mult: float = 0.75,
    document_id: str | None = None,
):
    query_filter = get_document_filter(
        document_id
    )

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=query_filter,
        limit=fetch_limit,
        with_payload=True,
        with_vectors=True,
    )

    candidates = list(
        results.points
    )

    if not candidates:
        return []

    selected = []

    while (
        len(selected) < limit
        and candidates
    ):
        best_candidate = None
        best_mmr_score = float("-inf")

        for candidate in candidates:

            # Qdrant already calculates
            # query relevance score.
            relevance_score = candidate.score

            if selected:
                max_similarity = max(
                    cosine_similarity(
                        candidate.vector,
                        selected_point.vector,
                    )
                    for selected_point in selected
                )
            else:
                max_similarity = 0.0

            mmr_score = (
                lambda_mult
                * relevance_score
                - (1 - lambda_mult)
                * max_similarity
            )

            if (
                mmr_score
                > best_mmr_score
            ):
                best_mmr_score = mmr_score
                best_candidate = candidate

        if best_candidate is None:
            break

        selected.append(
            best_candidate
        )

        candidates.remove(
            best_candidate
        )

    return selected


# --------------------------------------------------
# DELETE DOCUMENT CHUNKS
# --------------------------------------------------

def delete_document_chunks(
    document_id: str,
):
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(
                            value=str(document_id)
                        ),
                    )
                ]
            )
        ),
        wait=True,
    )