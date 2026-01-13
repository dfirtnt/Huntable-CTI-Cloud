"""Initialize PostgreSQL database with pgvector extension.

This script:
1. Connects to the RDS PostgreSQL instance
2. Creates the pgvector extension
3. Verifies the extension is installed correctly
"""
import asyncio
import asyncpg
import json
import boto3
import os
from pathlib import Path


async def init_database():
    """Initialize the database with pgvector extension."""

    # Retrieve database credentials from AWS Secrets Manager
    secret_arn = os.environ.get("DATABASE_SECRET_ARN")
    if not secret_arn:
        print("[ERROR] DATABASE_SECRET_ARN environment variable not set")
        print("Please set it to your RDS password secret ARN:")
        print("  export DATABASE_SECRET_ARN='arn:aws:secretsmanager:REGION:ACCOUNT:secret:...'")
        return False

    aws_region = os.environ.get("AWS_REGION", "us-east-1")
    print(f"Retrieving database credentials from Secrets Manager...")
    print(f"Secret ARN: {secret_arn}")

    secrets_client = boto3.client("secretsmanager", region_name=aws_region)
    secret_value = secrets_client.get_secret_value(SecretId=secret_arn)

    db_config = json.loads(secret_value["SecretString"])

    print(f"Connecting to PostgreSQL at {db_config['host']}...")

    try:
        # Connect to database (RDS requires SSL)
        conn = await asyncpg.connect(
            host=db_config["host"],
            port=db_config["port"],
            database=db_config["dbname"],
            user=db_config["username"],
            password=db_config["password"],
            timeout=30,
            ssl="require"
        )

        print("[OK] Connected successfully")

        # Check PostgreSQL version
        version = await conn.fetchval("SELECT version()")
        print(f"[OK] PostgreSQL version: {version.split(',')[0]}")

        # Create pgvector extension
        print("Creating pgvector extension...")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("[OK] pgvector extension created")

        # Verify extension is installed
        extensions = await conn.fetch(
            "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'"
        )

        if extensions:
            ext = extensions[0]
            print(f"[OK] pgvector extension installed: version {ext['extversion']}")
        else:
            print("[ERROR] pgvector extension not found")
            return False

        # Test vector functionality
        print("\nTesting vector functionality...")
        await conn.execute("CREATE TABLE IF NOT EXISTS vector_test (id serial PRIMARY KEY, embedding vector(3))")
        await conn.execute("INSERT INTO vector_test (embedding) VALUES ('[1,2,3]')")
        result = await conn.fetchrow("SELECT embedding FROM vector_test LIMIT 1")
        print(f"[OK] Vector test successful: {result['embedding']}")

        # Clean up test table
        await conn.execute("DROP TABLE vector_test")

        await conn.close()
        print("\n[OK] Database initialization complete!")
        return True

    except asyncpg.exceptions.PostgresError as e:
        print(f"[ERROR] PostgreSQL error: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(init_database())
    exit(0 if success else 1)
