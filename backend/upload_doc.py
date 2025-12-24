from doc_processing.docs_to_json import convert_to_json_and_upload
from search_query.search_query import (
    map_documents_for_search,
    upload_documents_to_search,
    load_json_documents_from_blob,
)
from _credentials import (
    blob_connection_string,
)
from _config import (
    CONTAINER_NAME,
    INDEX_NAME,
    SEARCH_NAME,
    RG_NAME,
)
from _credentials import (
    subscription_id,
    credential,
)
from _utils import logger
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from pathlib import Path
from _utils import (
    get_search_admin_key,
)

convert_to_json_and_upload("docs/")

for txt_file in Path("scraping/MITRE/").rglob("*.txt"):
    convert_to_json_and_upload(str(txt_file.parent))

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

documents = load_json_documents_from_blob(blob_connection_string, CONTAINER_NAME)

logger.info(f"Loaded {len(documents)} documents")

doc_to_upload = map_documents_for_search(documents)

logger.info(f"Mapped {len(doc_to_upload)} documents for upload")
# logger.info(f"Sample document: {doc_to_upload[0] if doc_to_upload else 'No documents'}")

upload_documents_to_search(search_client, doc_to_upload)
