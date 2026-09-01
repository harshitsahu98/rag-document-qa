from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://raguser:ragpassword@127.0.0.1:5433/ragdb"

print("Using:", DATABASE_URL)

try:
    engine = create_engine(DATABASE_URL)

    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        print("PostgreSQL connection successful!")
        print(result.scalar())

except Exception as e:
    print("PostgreSQL connection failed:")
    print(e)