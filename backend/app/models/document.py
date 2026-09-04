import uuid

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
)

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.sql import func

from app.db.database import Base


class Document(Base):

    __tablename__ = "documents"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    filename = Column(
        String,
        nullable=False,
    )

    file_path = Column(
        String,
        nullable=False,
    )

    status = Column(
        String,
        nullable=False,
    )

    pages = Column(
        Integer,
        default=0,
    )

    chunks = Column(
        Integer,
        default=0,
    )

    created_at = Column(
        DateTime,
        server_default=func.now(),
    )