from search_query.search_query import (
    map_documents_for_search,
    upload_documents_to_search,
    load_json_documents_from_blob,
)
from _credentials import blob_connection_string
from _config import CONTAINER_NAME, INDEX_NAME, SEARCH_NAME
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

credential = AzureKeyCredential("Jk8pbmuzlO8zpCTTkveSp6E5WvPZTwxRpLfwgJmQPHAzSeCFUa02")

endpoint = f"https://{SEARCH_NAME}.search.windows.net"

search_client = SearchClient(
    endpoint=endpoint,
    index_name=INDEX_NAME,
    credential=credential,
)

documents = load_json_documents_from_blob(blob_connection_string, CONTAINER_NAME)

doc_to_upload = map_documents_for_search(documents)

upload_documents_to_search(search_client, doc_to_upload)
