import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    conn_str = os.getenv('DATABASE_URL').replace('postgresql+asyncpg://', 'postgresql://').split('?')[0]
    conn = await asyncpg.connect(conn_str, ssl='require')

    tables = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")

    print("\nDatabase tables created:")
    for t in tables:
        print(f"  - {t['table_name']}")

    print(f"\nTotal: {len(tables)} tables")
    await conn.close()

asyncio.run(main())
