"""
One-off: unblock session afb1d4df (042326_Hendershott chat) that was created
with gemini-2.5-flash (1M context) before the default flipped to pro (2M).
Updates session_templates.ai_model to gemini-2.5-pro, resets the session
status to uploading, and re-fires ai_process_task.
"""
import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

SESSION_ID = "afb1d4df-6e0f-46aa-aeda-33f58e61d54d"


async def main():
    url = os.environ["DATABASE_URL"].replace("postgres://", "postgresql+asyncpg://").replace(
        "postgresql://", "postgresql+asyncpg://"
    )
    e = create_async_engine(url)
    async with e.begin() as c:
        # 1. Flip model on the template
        await c.execute(
            text(
                """
                UPDATE session_templates
                   SET ai_model = 'gemini-2.5-pro',
                       updated_at = now()
                 WHERE session_id = CAST(:sid AS uuid)
                """
            ),
            {"sid": SESSION_ID},
        )
        # 2. Reset session status so ingest can re-run
        await c.execute(
            text(
                """
                UPDATE sessions
                   SET status = 'uploading',
                       updated_at = now()
                 WHERE id = CAST(:sid AS uuid)
                """
            ),
            {"sid": SESSION_ID},
        )
        # 3. Dump current state
        row = (
            await c.execute(
                text(
                    """
                    SELECT s.status, t.ai_model, t.ai_mode, t.ai_pipeline
                      FROM sessions s
                      JOIN session_templates t ON t.session_id = s.id
                     WHERE s.id = CAST(:sid AS uuid)
                    """
                ),
                {"sid": SESSION_ID},
            )
        ).mappings().first()
        print("after_update =", dict(row) if row else None)
    await e.dispose()

    # 4. Re-fire the ingest task via Celery
    from app.tasks.ingest import ingest_task
    ingest_task.delay(session_id=SESSION_ID)
    print(f"queued ingest_task for {SESSION_ID}")


asyncio.run(main())
