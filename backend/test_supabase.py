from app.services.supabase_service import supabase


def test_supabase():
    print("Testing Supabase connection...")

    result = supabase.storage.list_buckets()

    print("Connected successfully!")
    print("Available buckets:")

    for bucket in result:
        print("-", bucket.name)


if __name__ == "__main__":
    test_supabase()