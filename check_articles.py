import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    conn_str = os.getenv('DATABASE_URL').replace('postgresql+asyncpg://', 'postgresql://').split('?')[0]
    conn = await asyncpg.connect(conn_str, ssl='require')

    # Check article count
    article_count = await conn.fetchval("SELECT COUNT(*) FROM articles")
    print(f"\nTotal articles in database: {article_count}")

    if article_count > 0:
        # Get recent articles
        articles = await conn.fetch("""
            SELECT id, title, source_id, published_at, article_metadata, created_at
            FROM articles
            ORDER BY created_at DESC
            LIMIT 5
        """)

        print("\nMost recent articles:")
        for article in articles:
            import json
            metadata = json.loads(article['article_metadata']) if article['article_metadata'] else {}
            hunt_score = metadata.get('hunt_score', 0.0)

            print(f"\n  ID: {article['id']}")
            print(f"  Title: {article['title'][:80]}...")
            print(f"  Source: {article['source_id']}")
            print(f"  Hunt Score: {hunt_score}")
            print(f"  Created: {article['created_at']}")

    # Check sources
    source_count = await conn.fetchval("SELECT COUNT(*) FROM sources")
    print(f"\nTotal sources configured: {source_count}")

    await conn.close()

asyncio.run(main())
