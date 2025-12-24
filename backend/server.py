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


app = FastAPI(title="AI Chat Backend", version="0.1.0")

# CORS: allow the Vite dev server and other local origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat")
def chat(req: QueryRequest):
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Missing 'question'")

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
        results = search_index(search_client, vector=query_vector, top_k=25)

        # 3) Build context from relevant hits; fallback if none
        threshold = 0.55
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
                top_k=20,
                select=["content", "source"],
            )
            for hit in keyword_hits:
                doc = hit.get("document", {})
                content = doc.get("content", "")
                source = doc.get("source", "")
                if content:
                    context_parts.append(f"Content: {content}\nSource: {source}\n")

        context = "\n".join(context_parts)

        # 4) Compose prompt and get completion
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a cybersecurity specialist. Use the provided context to answer the user's question. Do not use information outside the context. If the context is blank say you don't know."
                ),
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}",
            },
        ]

        answer = get_openai_completion(
            messages,
            GPT_DEPLOYMENT_NAME,
            embed_endpoint,
            embed_api_key,
        )

        return {"answer": answer}

    except HTTPException:
        raise
    except Exception as e:
        # Log-friendly error response
        raise HTTPException(status_code=500, detail=f"Server error: {e}")
