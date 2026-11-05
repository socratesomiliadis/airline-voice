"""Engine lifetime and session factory. No schema creation or automatic commits."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class Database:
    def __init__(self, url: str) -> None:
        self.engine = create_async_engine(url, pool_pre_ping=True)
        self.sessions = async_sessionmaker[AsyncSession](self.engine, expire_on_commit=False)

    async def dispose(self) -> None:
        await self.engine.dispose()
