from search_query.search_query import search_index
from _credentials import (
    subscription_id,
    credential,
    embed_endpoint,
    embed_api_key,
)
from _config import (
    INDEX_NAME,
    SEARCH_NAME,
    RG_NAME,
    EMBEDDING_DEPLOYMENT_NAME,
    GPT_DEPLOYMENT_NAME,
)
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from _utils import (
    get_search_admin_key,
    get_openai_embedding,
    get_openai_completion,
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

admin_key = get_search_admin_key(
    credential,
    subscription_id,
    RG_NAME,
    SEARCH_NAME,
)

search_credential = AzureKeyCredential(admin_key)
search_endpoint = f"https://{SEARCH_NAME}.search.windows.net"

search_client = SearchClient(
    endpoint=search_endpoint,
    index_name=INDEX_NAME,
    credential=search_credential,
)

input_text = "cybersecurity"  # Example query

print(f"Searching for: {input_text}")

# 1. Generate Embedding
query_vector = get_openai_embedding(
    input_text,
    EMBEDDING_DEPLOYMENT_NAME,
    embed_endpoint,
    embed_api_key,
)

# 2. Search
results = search_index(search_client, vector=query_vector, top_k=100)

# Check if we have relevant results from vector search
if not results or not any(hit["score"] > 0.55 for hit in results):
    print("No relevant vector search results found. Falling back to keyword search...")

# 3. Construct Context
context = ""
for hit in results:
    if hit["score"] > 0.55:  # Filter by relevance
        logger.info(
            f"Document: {hit['document'].get('source', 'Unknown')} (Content: {hit['document'].get('content', '')[:100]}...) Score: {hit['score']}"
        )
        context += f"Content: {hit['document'].get('content', '')}\nSource: {hit['document'].get('source', '')}\n\n"

if not context:
    print("No relevant documents found.")
else:
    # 4. Generate Answer
    logger.info(
        f"Found {len([hit for hit in results if hit['score'] > 0.5])} qualified documents"
    )
    messages = [
        {
            "role": "system",
            "content": "You are a cybersecurity specialist. Use the provided context to answer the user's question. Do not use information outside the context.",
        },
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {input_text}"},
    ]

    print("Generating answer...")
    answer = get_openai_completion(
        messages,
        GPT_DEPLOYMENT_NAME,
        embed_endpoint,  # Using same endpoint
        embed_api_key,  # Using same key
    )

    print(f"\nQuestion: {input_text}")
    print(f"Answer: {answer}")
