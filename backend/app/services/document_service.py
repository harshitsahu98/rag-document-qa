import re
import os
import tempfile

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.supabase_service import supabase
from app.core.config import SUPABASE_BUCKET


def clean_pdf_text(text: str) -> str:
    # Fix words broken across lines with a hyphen
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # Normalize excessive spaces but preserve newlines
    text = re.sub(r"[ \t]+", " ", text)

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_pdf_text(file_path: str):
    """
    Extract and clean text from a local PDF file.
    """

    loader = PyMuPDFLoader(file_path)

    documents = loader.load()

    for document in documents:
        document.page_content = clean_pdf_text(
            document.page_content
        )

    return documents


def download_pdf_from_supabase(
    storage_path: str,
):
    """
    Download a PDF from Supabase Storage and save it
    temporarily on the Celery worker.
    """

    pdf_bytes = (
        supabase.storage
        .from_(SUPABASE_BUCKET)
        .download(storage_path)
    )

    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pdf",
    )

    temp_file.write(pdf_bytes)

    temp_file.close()

    return temp_file.name


def delete_temp_file(
    file_path: str,
):
    """
    Delete the temporary PDF after processing.
    """

    if os.path.exists(file_path):
        os.remove(file_path)


def split_documents(documents):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=700,
        chunk_overlap=100,
        separators=[
            "\n\n",
            "\n•",
            "\n",
            ". ",
            " ",
            "",
        ],
    )

    return splitter.split_documents(documents)