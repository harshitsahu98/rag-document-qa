import ssl

from celery import Celery
from app.core.config import REDIS_URL


celery_app = Celery(
    "rag_document_qa",
    broker=REDIS_URL,
    backend=REDIS_URL,
)


celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,

    broker_use_ssl={
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
    },

    redis_backend_use_ssl={
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
    },

    imports=(
        "app.tasks.test_task",
        "app.tasks.document_tasks",
    ),
)