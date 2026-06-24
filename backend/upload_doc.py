from doc_processing.docs_to_json import convert_to_json_and_upload, upload_backup
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

from pathlib import Path
from _credentials import (
    subscription_id,
    credential,
)
from _utils import logger
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from _utils import (
    get_search_admin_key,
)
import time
import json

timings = {}


def _calculate_total_size(documents: list[dict]) -> int:
    return sum(len(json.dumps(doc).encode("utf-8")) for doc in documents)


# Quick upload
# upload_backup("backup/")

# Use for new documents!
# convert_to_json_and_upload("docs/")

overall_start = time.perf_counter()

# Process MITRE directories (collect unique parent directories to avoid duplicates)
mitre_dirs = set()
for txt_file in Path("scraping/MITRE/").rglob("*.txt"):
    mitre_dirs.add(str(txt_file.parent))

mitre_start = time.perf_counter()
for mitre_dir in mitre_dirs:
    print(f"\n{'='*60}")
    print(f"Processing directory: {mitre_dir}")
    print(f"{'='*60}")
    convert_to_json_and_upload(mitre_dir)
timings["mitre_processing"] = time.perf_counter() - mitre_start

# Darkreader directories (collect unique parent directories to avoid duplicates)
darkreader_dirs = set()
for txt_file in Path("scraping/darkreader/").rglob("*.txt"):
    darkreader_dirs.add(str(txt_file.parent))

darkreader_start = time.perf_counter()
for darkreader_dir in darkreader_dirs:
    print(f"\n{'='*60}")
    print(f"Processing directory: {darkreader_dir}")
    print(f"{'='*60}")
    convert_to_json_and_upload(darkreader_dir)
timings["darkreader_processing"] = time.perf_counter() - darkreader_start

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

load_start = time.perf_counter()
documents = load_json_documents_from_blob(blob_connection_string, CONTAINER_NAME)
timings["load_from_blob"] = time.perf_counter() - load_start

loaded_size = _calculate_total_size(documents)
logger.info(f"Loaded {len(documents)} documents (total {loaded_size / 1024:.2f} KB)")

map_start = time.perf_counter()
doc_to_upload = map_documents_for_search(documents)
timings["map_for_search"] = time.perf_counter() - map_start

mapped_size = _calculate_total_size(doc_to_upload)
logger.info(
    f"Mapped {len(doc_to_upload)} documents for upload (total {mapped_size / 1024:.2f} KB)"
)

upload_start = time.perf_counter()
upload_documents_to_search(search_client, doc_to_upload)
timings["upload_to_search"] = time.perf_counter() - upload_start

timings["total"] = time.perf_counter() - overall_start

logger.info("=" * 60)
logger.info("TIMING SUMMARY")
logger.info("-" * 60)
for phase, elapsed in timings.items():
    logger.info(f"  {phase:<20s} {elapsed:>8.2f}s")
logger.info("=" * 60)
logger.info("SIZE SUMMARY")
logger.info("-" * 60)
logger.info(
    f"  Loaded from blob:    {len(documents):>6} docs, {loaded_size / 1024:.2f} KB"
)
logger.info(
    f"  Mapped for search:   {len(doc_to_upload):>6} docs, {mapped_size / 1024:.2f} KB"
)
logger.info("=" * 60)

with open("upload_summary.txt", "w") as f:
    f.write("TIMING SUMMARY\n")
    f.write("-" * 60 + "\n")
    for phase, elapsed in timings.items():
        f.write(f"  {phase:<20s} {elapsed:>8.2f}s\n")
    f.write("\n")
    f.write("SIZE SUMMARY\n")
    f.write("-" * 60 + "\n")
    f.write(
        f"  Loaded from blob:    {len(documents):>6} docs, {loaded_size / 1024:.2f} KB\n"
    )
    f.write(
        f"  Mapped for search:   {len(doc_to_upload):>6} docs, {mapped_size / 1024:.2f} KB\n"
    )
    f.write("=" * 60 + "\n")
