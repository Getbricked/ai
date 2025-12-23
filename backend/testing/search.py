from search_query.search_query import (
    map_documents_for_search,
    upload_documents_to_search,
    load_json_documents_from_blob,
    search_index,
)
from _credentials import (
    blob_connection_string,
    subscription_id,
    credential,
    embed_endpoint,
    embed_api_key,
)
from _config import (
    CONTAINER_NAME,
    INDEX_NAME,
    SEARCH_NAME,
    RG_NAME,
    EMBEDDING_DEPLOYMENT_NAME,
)
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from _utils import (
    get_search_admin_key,
    get_openai_embedding,
)
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

admin_key = get_search_admin_key(
    credential,
    subscription_id,
    RG_NAME,
    SEARCH_NAME,
)

search_credential = AzureKeyCredential(admin_key)

search_endpoint = f"https://{SEARCH_NAME}.search.windows.net"

# Add debugging logs
# logger.info(f"Endpoint: {search_endpoint}")
# logger.info(f"Index name: {INDEX_NAME}")

search_client = SearchClient(
    endpoint=search_endpoint,
    index_name=INDEX_NAME,
    credential=search_credential,
)

input_text = "father"

query_vector = get_openai_embedding(
    input_text,
    EMBEDDING_DEPLOYMENT_NAME,
    embed_endpoint,
    embed_api_key,
)

results = search_index(search_client, vector=query_vector, top_k=100)

print(f"\nFound {len(results)} results\n")

for i, hit in enumerate(results, 1):
    if hit["score"] > 0.65:
        print(f"\n[Result {i}]")
        print(f"Score: {hit['score']}")
        print(f"Document ID: {hit['document'].get('id', 'N/A')}")
        print(f"Content: {hit['document'].get('content', 'N/A')[:200]}...")
        print(f"Category: {hit['document'].get('category', 'N/A')}")
        print(f"Source: {hit['document'].get('source', 'N/A')}")
        print("-" * 80)
