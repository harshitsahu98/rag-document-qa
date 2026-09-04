import os

from dotenv import load_dotenv


# Load .env locally.
# On Render, variables are provided by the environment.
load_dotenv()


def get_required_env(
    name: str,
) -> str:
    value = os.getenv(name)

    if not value:
        raise ValueError(
            f"{name} environment variable is not set"
        )

    return value


# Required environment variables
DATABASE_URL = get_required_env(
    "DATABASE_URL"
)

REDIS_URL = get_required_env(
    "REDIS_URL"
)

QDRANT_URL = get_required_env(
    "QDRANT_URL"
)

GEMINI_API_KEY = get_required_env(
    "GEMINI_API_KEY"
)

GROQ_API_KEY = get_required_env(
    "GROQ_API_KEY"
)

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b",
)


# Optional environment variables
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

SUPABASE_URL = get_required_env(
    "SUPABASE_URL"
)

SUPABASE_KEY = get_required_env(
    "SUPABASE_KEY"
)

SUPABASE_BUCKET = get_required_env(
    "SUPABASE_BUCKET"
)