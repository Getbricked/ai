import os
import uuid
import json
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from azure.search.documents import SearchClient
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
    get_openai_embedding,
    get_openai_completion,
)

from search_query.search_query import search_index


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
    # Allow any https://*.devtunnels.ms origin (FastAPI supports regex)
    allow_origin_regex=r"https://.*\.devtunnels\.ms",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_search_client() -> SearchClient:
    admin_key = get_search_admin_key(
        credential,
        subscription_id,
        RG_NAME,
        SEARCH_NAME,
    )
    search_credential = AzureKeyCredential(admin_key)
    search_endpoint = f"https://{SEARCH_NAME}.search.windows.net"
    return SearchClient(
        endpoint=search_endpoint,
        index_name=INDEX_NAME,
        credential=search_credential,
    )


def save_session_to_file(session_data: dict) -> bool:
    """Save session as JSON to frontend/sessions folder."""
    try:
        # Create sessions folder if it doesn't exist
        sessions_dir = Path(__file__).parent.parent / "frontend" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)

        # Create filename from session ID
        filename = f"session_{session_data['session_id']}.json"
        filepath = sessions_dir / filename

        # Write JSON file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)

        print(f"Session saved to {filepath}")
        return True
    except Exception as e:
        print(f"Failed to save session: {e}")
        return False


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/new-session", response_model=NewSessionResponse)
def new_session():
    """Create a new chat session with a unique ID."""
    session_id = str(uuid.uuid4())
    sessions[session_id] = []
    return NewSessionResponse(session_id=session_id)


@app.post("/api/save-session")
def save_session(req: SaveSessionRequest):
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
def chat(req: QueryRequest):
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Missing 'question'")

    # Initialize session if not provided
    session_id = req.session_id
    if not session_id:
        session_id = str(uuid.uuid4())
        sessions[session_id] = []

    # Ensure session exists
    if session_id not in sessions:
        sessions[session_id] = []

    try:
        search_client = get_search_client()

        # 1) Embed the question
        query_vector = get_openai_embedding(
            question,
            EMBEDDING_DEPLOYMENT_NAME,
            embed_endpoint,
            embed_api_key,
        )

        # 2) Vector search
        results = search_index(search_client, vector=query_vector, top_k=100)

        # 3) Build context from relevant hits; fallback if none
        threshold = 0.6
        context_parts = []
        for hit in results:
            score = hit.get("score") or 0.0
            if score and score > threshold:
                doc = hit.get("document", {})
                content = doc.get("content", "")
                source = doc.get("source", "")
                context_parts.append(f"Content: {content}\nSource: {source}\n")
                context_parts.append(
                    f"Content: {content}\nSource: {source}\nScore: {score}\n"
                )
                print(f"Content: {content}, Score: {score}")

        # Optional fallback: keyword search when vector yields nothing
        if not context_parts:
            keyword_hits = search_index(
                search_client,
                query_text=question,
                top_k=100,
                select=["content", "source"],
            )
            for hit in keyword_hits:
                doc = hit.get("document", {})
                content = doc.get("content", "")
                source = doc.get("source", "")
                if content:
                    context_parts.append(f"Content: {content}\nSource: {source}\n")

        context = "\n".join(context_parts)

        # 4) Compose prompt with conversation history and get completion
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a cybersecurity specialist. Use the provided context to "
                    "answer the user's question. Do not use your own database to answer!."
                    "If there is a link attached to the answer, format it with markdown and put at the end of the sentence as [More info](link)."
                ),
            },
        ]

        # Add conversation history to messages
        for msg in sessions[session_id]:
            messages.append(msg)

        # Add current question
        messages.append(
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}",
            }
        )

        answer = get_openai_completion(
            messages,
            GPT_DEPLOYMENT_NAME,
            embed_endpoint,
            embed_api_key,
        )

        # Store the exchange in session history
        sessions[session_id].append({"role": "user", "content": question})
        sessions[session_id].append({"role": "assistant", "content": answer})

        return {"answer": answer, "session_id": session_id}

    except HTTPException:
        raise
    except Exception as e:
        # Log-friendly error response
        raise HTTPException(status_code=500, detail=f"Server error: {e}")
