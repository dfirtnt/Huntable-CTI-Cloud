#!/usr/bin/env python3
"""Quick script to check database contents"""
import asyncio
import asyncpg
import urllib.parse
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Parse DATABASE_URL from .env
db_url = os.getenv("DATABASE_URL")

# Extract connection params
parts = db_url.replace("postgresql+asyncpg://", "").split("@")
user_pass = parts[0].split(":")
user = user_pass[0]
password = urllib.parse.unquote(user_pass[1])
host_db = parts[1].split("/")
host_port = host_db[0].split(":")
host = host_port[0]
port = int(host_port[1])
database = host_db[1]

async def check_database():
    try:
        # Connect to database
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            ssl="require"
        )

        print("✓ Connected to database successfully\n")

        # Check if tables exist
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)

        print(f"Tables found: {len(tables)}")
        for table in tables:
            print(f"  - {table['table_name']}")

        print()

        # Check for articles
        if any(t['table_name'] == 'articles' for t in tables):
            article_count = await conn.fetchval("SELECT COUNT(*) FROM articles")
            print(f"Articles in database: {article_count}")

            if article_count > 0:
                # Get sample article info
                sample = await conn.fetchrow("""
                    SELECT id, title, source_id, published_at, word_count, processing_status
                    FROM articles
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                print(f"\nMost recent article:")
                print(f"  ID: {sample['id']}")
                print(f"  Title: {sample['title'][:80]}...")
                print(f"  Published: {sample['published_at']}")
                print(f"  Word count: {sample['word_count']}")
                print(f"  Status: {sample['processing_status']}")
        else:
            print("Articles table not found - schema not migrated")

        print()

        # Check for sources
        if any(t['table_name'] == 'sources' for t in tables):
            source_count = await conn.fetchval("SELECT COUNT(*) FROM sources")
            print(f"Sources in database: {source_count}")
        else:
            print("Sources table not found - schema not migrated")

        await conn.close()

    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_database())
