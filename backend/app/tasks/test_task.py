from app.core.celery_app import celery_app


@celery_app.task
def add_numbers(a: int, b: int):
    return a + b