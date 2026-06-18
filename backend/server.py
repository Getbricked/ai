import os
import uuid
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from azure.search.documents.aio import SearchClient as AsyncSearchClient
from azure.core.credentials import AzureKeyCredential

from _config import (
    INDEX_NAME,
    SEARCH_NAME,
    RG_NAME,
    EMBEDDING_DEPLOYMENT_NAME,
    GPT_DEPLOYMENT_NAME,
)
from _credentials import (
    subscription_id,
    credential,
    embed_endpoint,
    embed_api_key,
)
from _utils import (
    get_search_admin_key,
    get_openai_embedding_async,
    get_openai_completion_async,
)

from search_query.search_query import search_index_async

logger = logging.getLogger(__name__)


# Load security terms that trigger keyword search when present in a question
def _load_security_terms() -> list:
    try:
        terms_path = Path(__file__).parent / "security_terms.txt"
        if not terms_path.exists():
            return []
        with open(terms_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return []


SECURITY_TERMS = _load_security_terms()


class QueryRequest(BaseModel):
    question: str
    session_id: str = None


class NewSessionResponse(BaseModel):
    session_id: str


class SaveSessionRequest(BaseModel):
    session_id: str
    user_id: str = "user_default"
    messages: list


app = FastAPI(title="AI Chat Backend", version="0.1.0")

# Store active sessions with conversation history
# In production, use Redis or database for persistence
sessions = {}

# CORS: allow local Vite dev server plus Azure Dev Tunnels origins
extra_origins = [
    o.strip() for o in os.environ.get("EXTRA_ORIGINS", "").split(",") if o.strip()
]
allow_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
] + extra_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_search_client = None


def _get_search_admin_key():
    return get_search_admin_key(
        credential,
        subscription_id,
        RG_NAME,
        SEARCH_NAME,
    )


async def get_search_client() -> AsyncSearchClient:
    global _search_client
    if _search_client is None:
        admin_key = _get_search_admin_key()
        search_credential = AzureKeyCredential(admin_key)
        search_endpoint = f"https://{SEARCH_NAME}.search.windows.net"
        _search_client = AsyncSearchClient(
            endpoint=search_endpoint,
            index_name=INDEX_NAME,
            credential=search_credential,
        )
    return _search_client


def save_session_to_file(session_data: dict) -> bool:
    """Save session as JSON to frontend/sessions folder."""
    try:
        sessions_dir = Path(__file__).parent.parent / "frontend" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)

        filename = f"session_{session_data['session_id']}.json"
        filepath = sessions_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)

        logger.info("Session saved to %s", filepath)
        return True
    except Exception as e:
        logger.error("Failed to save session: %s", e)
        return False


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/new-session", response_model=NewSessionResponse)
async def new_session():
    """Create a new chat session with a unique ID."""
    session_id = str(uuid.uuid4())
    sessions[session_id] = []
    return NewSessionResponse(session_id=session_id)


@app.post("/api/save-session")
async def save_session(req: SaveSessionRequest):
    """Save a chat session to disk as JSON."""
    try:
        session_data = {
            "session_id": req.session_id,
            "user_id": req.user_id,
            "created_at": datetime.now().isoformat(),
            "messages": req.messages,
        }

        success = save_session_to_file(session_data)

        if success:
            return {"status": "saved", "session_id": req.session_id}
        else:
            raise HTTPException(status_code=500, detail="Failed to save session")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving session: {e}")


@app.post("/api/chat")
async def chat(req: QueryRequest):
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Missing 'question'")

    session_id = req.session_id
    if not session_id:
        session_id = str(uuid.uuid4())
        sessions[session_id] = []

    if session_id not in sessions:
        sessions[session_id] = []

    try:
        search_client = await get_search_client()

        seen_ids = set()
        context_parts = []

        embedding_task = asyncio.create_task(
            get_openai_embedding_async(
                question,
                EMBEDDING_DEPLOYMENT_NAME,
                embed_endpoint,
                embed_api_key,
            )
        )

        q_lower = question.lower()
        matches = [t for t in SECURITY_TERMS if t and t.lower() in q_lower]
        keyword_task = None
        if matches:
            keyword_task = asyncio.create_task(
                search_index_async(
                    search_client,
                    query_text=question,
                    top_k=10,
                    select=["content", "source"],
                )
            )

        if keyword_task:
            try:
                keyword_results = await keyword_task
                for hit in keyword_results:
                    doc = hit.get("document", {})
                    doc_id = doc.get("id")
                    content = doc.get("content", "")
                    source = doc.get("source", "")
                    if not content:
                        continue
                    if doc_id and doc_id in seen_ids:
                        continue
                    context_parts.append(f"Content: {content}\nSource: {source}\n")
                    if doc_id:
                        seen_ids.add(doc_id)
            except Exception as e:
                logger.error("Keyword search failed: %s", e)

        query_vector = await embedding_task

        vector_results = await search_index_async(
            search_client, vector=query_vector, top_k=100
        )

        threshold = 0.6
        for hit in vector_results:
            score = hit.get("score") or 0.0
            if score and score > threshold:
                doc = hit.get("document", {})
                doc_id = doc.get("id")
                if doc_id and doc_id in seen_ids:
                    continue
                content = doc.get("content", "")
                source = doc.get("source", "")
                context_parts.append(
                    f"Content: {content}\nSource: {source}\nScore: {score}\n"
                )
                if doc_id:
                    seen_ids.add(doc_id)

        context = "\n".join(context_parts)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a cybersecurity specialist. Use the provided context to "
                    "answer the user's question. Do not use your own database to answer!."
                    "If there is a link attached to the answer, "
                    "format it with markdown and put at the end of the sentence as "
                    "[More info](link)."
                ),
            },
        ]

        for msg in sessions[session_id]:
            messages.append(msg)

        messages.append(
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}",
            }
        )

        answer = await get_openai_completion_async(
            messages,
            GPT_DEPLOYMENT_NAME,
            embed_endpoint,
            embed_api_key,
        )

        sessions[session_id].append({"role": "user", "content": question})
        sessions[session_id].append({"role": "assistant", "content": answer})

        return {"answer": answer, "session_id": session_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {e}")
