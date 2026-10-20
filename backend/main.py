"""
ChainTrace API. Shared and frozen after kickoff: /health, CORS, and the two route files.

Run:  uvicorn main:app --reload --port 8000     (from the backend/ folder)
Docs: http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from contract.schemas import CONTRACT_VERSION
import routes_engine
import routes_product

app = FastAPI(title="ChainTrace API", version=CONTRACT_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"status": "ok", "contract_version": CONTRACT_VERSION}


app.include_router(routes_engine.router)
app.include_router(routes_product.router)
