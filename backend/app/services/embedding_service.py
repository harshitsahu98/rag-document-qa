import os
import time

from dotenv import load_dotenv

from langchain_google_genai import (
    GoogleGenerativeAIEmbeddings,
)

from langchain_groq import ChatGroq


# ---------------------------------
# LOAD ENVIRONMENT VARIABLES
# ---------------------------------

load_dotenv()


GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY"
)


if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY environment variable is not set"
    )


if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY environment variable is not set"
    )


# ---------------------------------
# EMBEDDING MODEL
# ---------------------------------

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=GEMINI_API_KEY,
)


# ---------------------------------
# CHAT MODEL
# ---------------------------------

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    groq_api_key=GROQ_API_KEY,
    temperature=0,
)


# ---------------------------------
# QUERY EMBEDDING WITH RETRY
# ---------------------------------

def embed_query_with_retry(
    text: str,
    max_retries: int = 6,
):
    """
    Generate an embedding for one query.
    Retries with exponential backoff if
    Gemini temporarily rate-limits the request.
    """

    for attempt in range(max_retries):

        try:

            return embeddings.embed_query(
                text
            )

        except Exception as error:

            if attempt == max_retries - 1:
                raise

            wait_time = min(
                2 ** attempt,
                60,
            )

            print(
                f"Query embedding failed "
                f"(attempt {attempt + 1}/"
                f"{max_retries}): {error}"
            )

            print(
                f"Retrying in "
                f"{wait_time} seconds..."
            )

            time.sleep(
                wait_time
            )


# ---------------------------------
# DOCUMENT EMBEDDING WITH RETRY
# ---------------------------------

def embed_documents_with_retry(
    texts: list[str],
    max_retries: int = 6,
):
    """
    Generate embeddings for multiple document
    chunks together in one batch request.

    Retries with exponential backoff when the
    Gemini API rate limit is temporarily exceeded.
    """

    for attempt in range(max_retries):

        try:

            return embeddings.embed_documents(
                texts
            )

        except Exception as error:

            if attempt == max_retries - 1:
                raise

            wait_time = min(
                2 ** attempt,
                60,
            )

            print(
                f"Document embedding failed "
                f"(attempt {attempt + 1}/"
                f"{max_retries}): {error}"
            )

            print(
                f"Retrying in "
                f"{wait_time} seconds..."
            )

            time.sleep(
                wait_time
            )