from fastapi import FastAPI

from app.controllers import tariffs

app = FastAPI()
app.include_router(tariffs.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
