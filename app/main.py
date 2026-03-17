from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from sqlalchemy import text

app = FastAPI()


@app.get("/health")
async def health(db:AsyncSession = Depends(get_db)):
    db_okay = False
    try:
        await db.execute(text("SELECT 1"))
        db_okay = True 
    except Exception:
        pass

    return "healthy" if db_okay else "not healthy"
        

