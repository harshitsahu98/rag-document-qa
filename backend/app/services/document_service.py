import re

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter


def clean_pdf_text(text: str) -> str:
    # Fix words broken across lines with a hyphen
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # Normalize excessive spaces but preserve newlines
    text = re.sub(r"[ \t]+", " ", text)

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_pdf_text(file_path: str):
    loader = PyMuPDFLoader(file_path)

    documents = loader.load()

    # Clean every extracted page
    for document in documents:
        document.page_content = clean_pdf_text(
            document.page_content
        )

    return documents


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

    chunks = splitter.split_documents(documents)

    return chunks