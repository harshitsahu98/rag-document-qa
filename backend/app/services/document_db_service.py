from sqlalchemy.orm import Session

from app.models.document import Document


def get_all_documents(
    db: Session,
    limit: int = 20,
    offset: int = 0,
):
    return (
        db.query(Document)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

def delete_document_record(
    db: Session,
    document_id,
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if document is None:
        return None

    db.delete(document)
    db.commit()

    return document

def get_document_by_id(
    db: Session,
    document_id,
):
    return (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

def get_documents_count(
    db: Session,
):
    return (
        db.query(Document)
        .count()
    )