from search_query.search_query import (
    map_documents_for_search,
    upload_documents_to_search,
    load_json_documents_from_blob,
    search_index,
)
from _credentials import blob_connection_string, subscription_id, credential
from _config import CONTAINER_NAME, INDEX_NAME, SEARCH_NAME, RG_NAME
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from _utils import get_search_admin_key
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

endpoint = f"https://{SEARCH_NAME}.search.windows.net"

# Add debugging logs
logger.info(f"Endpoint: {endpoint}")
logger.info(f"Index name: {INDEX_NAME}")

search_client = SearchClient(
    endpoint=endpoint,
    index_name=INDEX_NAME,
    credential=search_credential,
)

documents = load_json_documents_from_blob(blob_connection_string, CONTAINER_NAME)

logger.info(f"Loaded {len(documents)} documents")

doc_to_upload = map_documents_for_search(documents)

logger.info(f"Mapped {len(doc_to_upload)} documents for upload")
logger.info(f"Sample document: {doc_to_upload[0] if doc_to_upload else 'No documents'}")

upload_documents_to_search(search_client, doc_to_upload)

print("\n" + "=" * 80)
print("Searching for: 'test'")
print("=" * 80)
results = search_index(search_client, query_text="test")

print(f"\nFound {len(results)} results\n")

for i, hit in enumerate(results, 1):
    print(f"\n[Result {i}]")
    print(f"Score: {hit['score']}")
    print(f"Document ID: {hit['document'].get('id', 'N/A')}")
    print(f"Content: {hit['document'].get('content', 'N/A')[:200]}...")
    print(f"Category: {hit['document'].get('category', 'N/A')}")
    print(f"Source: {hit['document'].get('source', 'N/A')}")
    print("-" * 80)
