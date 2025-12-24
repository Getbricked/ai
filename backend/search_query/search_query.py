from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes import SearchIndexerClient
from azure.search.documents.indexes.models import (
    SearchIndexer,
    SearchIndexerDataSourceConnection,
    SearchIndexerDataContainer,
)
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from typing import List, Dict, Any, Optional
import time


def load_json_documents_from_blob(
    connection_string: str, container_name: str, max_workers: int = 8
) -> List[Dict[str, Any]]:
    """
    Loads JSON documents from Azure Blob Storage in parallel for maximum speed.

    Args:
        connection_string: Azure Storage connection string
        container_name: Name of the blob container
        max_workers: Number of parallel workers for downloading blobs (default 8)

    Returns:
        List of document dictionaries
    """
    print(f"Loading JSON documents from container '{container_name}'...")

    try:
        blob_service_client = BlobServiceClient.from_connection_string(
            connection_string
        )
        container_client = blob_service_client.get_container_client(container_name)

        # Get list of all JSON blobs
        blob_names = [
            blob.name
            for blob in container_client.list_blobs()
            if blob.name.endswith(".json")
        ]

        if not blob_names:
            print("No .json files found in blob container.")
            return []

        print(f"Found {len(blob_names)} JSON files. Downloading in parallel...")

        documents = []
        processed_count = 0

        def download_and_parse_blob(blob_name: str) -> List[Dict[str, Any]]:
            """Download and parse a single blob."""
            try:
                blob_client = container_client.get_blob_client(blob_name)
                blob_data = blob_client.download_blob().readall()

                try:
                    data = json.loads(blob_data)

                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        return [data]
                    else:
                        print(
                            f"Warning: {blob_name} does not contain a valid JSON object or list."
                        )
                        return []

                except json.JSONDecodeError:
                    print(f"Warning: Could not decode JSON from {blob_name}.")
                    return []

            except Exception as e:
                print(f"Error processing blob {blob_name}: {e}")
                return []

        # Download and parse blobs in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_blob = {
                executor.submit(download_and_parse_blob, blob_name): blob_name
                for blob_name in blob_names
            }

            for future in as_completed(future_to_blob):
                blob_name = future_to_blob[future]
                processed_count += 1

                try:
                    blob_documents = future.result()
                    if blob_documents:
                        documents.extend(blob_documents)
                        print(
                            f"✅ Processed {blob_name} ({processed_count}/{len(blob_names)}) - {len(blob_documents)} docs"
                        )
                    else:
                        print(
                            f"⚠️ Processed {blob_name} ({processed_count}/{len(blob_names)}) - 0 docs"
                        )

                except Exception as e:
                    print(f"❌ Failed to process {blob_name}: {e}")

        if not documents:
            print("No valid documents found in blob container.")
            return []

        print(
            f"🎉 Successfully loaded {len(documents)} documents from {len(blob_names)} files."
        )
        return documents

    except Exception as e:
        print(f"Error loading documents from blob: {e}")
        raise


def upload_documents_to_search(
    search_client: SearchClient,
    documents: List[Dict[str, Any]],
    batch_size: int = 1000,
    max_workers: int = 4,
) -> bool:
    """
    Uploads documents to Azure AI Search index in parallel batches for maximum speed.

    Args:
        search_client: Initialized SearchClient instance
        documents: List of documents to upload
        batch_size: Number of documents per batch (max 1000 for Azure Search)
        max_workers: Number of parallel workers (default 4)

    Returns:
        True if all documents uploaded successfully, False otherwise
    """
    if not documents:
        print("No documents to upload.")
        return False

    total_docs = len(documents)
    print(
        f"Uploading {total_docs} documents in batches of {batch_size} with {max_workers} parallel workers..."
    )

    start_time = time.time()

    # Split into batches
    batches = [documents[i : i + batch_size] for i in range(0, total_docs, batch_size)]
    total_batches = len(batches)

    all_success = True
    total_uploaded = 0
    failed_batches = []

    def upload_single_batch(batch_data):
        """Upload a single batch and return results."""
        batch, batch_num = batch_data
        try:
            result = search_client.merge_or_upload_documents(documents=batch)
            success = all(r.succeeded for r in result)

            if success:
                return {
                    "success": True,
                    "batch_num": batch_num,
                    "count": len(batch),
                    "failed_docs": [],
                }
            else:
                failed_docs = [
                    (r.key, r.error_message) for r in result if not r.succeeded
                ]
                return {
                    "success": False,
                    "batch_num": batch_num,
                    "count": len(batch),
                    "failed_docs": failed_docs,
                }
        except Exception as e:
            return {
                "success": False,
                "batch_num": batch_num,
                "count": 0,
                "error": str(e),
            }

    # Upload batches in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all batch upload tasks
        batch_data = [(batch, i + 1) for i, batch in enumerate(batches)]
        future_to_batch = {
            executor.submit(upload_single_batch, data): data[1] for data in batch_data
        }

        # Process completed uploads
        for future in as_completed(future_to_batch):
            batch_num = future_to_batch[future]

            try:
                result = future.result()

                if result["success"]:
                    total_uploaded += result["count"]
                    print(
                        f"✅ Batch {result['batch_num']}/{total_batches} uploaded ({total_uploaded}/{total_docs} total)"
                    )
                else:
                    all_success = False
                    if "error" in result:
                        print(
                            f"❌ Batch {result['batch_num']}/{total_batches} failed: {result['error']}"
                        )
                        failed_batches.append(result["batch_num"])
                    else:
                        print(
                            f"⚠️ Batch {result['batch_num']}/{total_batches}: {len(result['failed_docs'])} documents failed"
                        )
                        for doc_key, error_msg in result["failed_docs"][
                            :5
                        ]:  # Show first 5 errors
                            print(f"  - Document {doc_key}: {error_msg}")

            except Exception as e:
                all_success = False
                print(f"❌ Batch {batch_num} raised exception: {e}")
                failed_batches.append(batch_num)

    elapsed_time = time.time() - start_time
    docs_per_sec = total_docs / elapsed_time if elapsed_time > 0 else 0

    if all_success:
        print(
            f"🎉 Successfully uploaded all {total_docs} documents in {elapsed_time:.2f}s ({docs_per_sec:.0f} docs/sec)"
        )
    else:
        print(
            f"⚠️ Upload completed with failures. {total_uploaded}/{total_docs} documents uploaded in {elapsed_time:.2f}s"
        )
        if failed_batches:
            print(f"Failed batches: {failed_batches}")

    return all_success


def search_index(
    search_client: SearchClient,
    query_text: Optional[str] = None,
    vector: Optional[List[float]] = None,
    vector_field: str = "content_vector",
    top_k: int = 10,
    filter: Optional[str] = None,
    select: Optional[List[str]] = None,
    semantic_configuration_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Perform a search against an Azure Search index using text and/or vector search.

    Args:
        search_client: Initialized SearchClient instance.
        query_text: Free-text query (can be None when performing pure vector search).
        vector: Optional embedding vector for vector similarity search.
        vector_field: Name of the vector field in the index (default "content_vector").
        top_k: Number of results to return.
        filter: OData filter expression.
        select: List of fields to include in results.
        semantic_configuration_name: Optional semantic configuration name for semantic search.

    Returns:
        List of hits where each hit is a dict: {"score": float, "document": dict}
    """
    if not query_text and not vector:
        raise ValueError("Either query_text or vector must be provided.")

    search_kwargs: Dict[str, Any] = {"top": top_k}
    if filter:
        search_kwargs["filter"] = filter
    if select:
        search_kwargs["select"] = select
    if semantic_configuration_name:
        search_kwargs["semantic_configuration_name"] = semantic_configuration_name

    try:
        if vector:
            # Use VectorizedQuery instead of VectorQuery
            vq = VectorizedQuery(
                vector=vector,  # Changed from 'value' to 'vector'
                k_nearest_neighbors=top_k,  # Add k parameter
                fields=vector_field,  # Changed from list to string
                kind="vector",  # Add required 'kind' parameter
            )
            # If query_text is None, pass None for pure vector search
            search_text = query_text if query_text is not None else None
            results = search_client.search(
                search_text=search_text, vector_queries=[vq], **search_kwargs
            )
        else:
            results = search_client.search(search_text=query_text, **search_kwargs)

        hits: List[Dict[str, Any]] = []
        for r in results:
            # r is already a dict-like object containing the document fields
            # Convert to plain dict to access all fields
            doc = dict(r)

            # Extract the search score (it's a key in the result)
            score = doc.pop("@search.score", None)

            # Remove other metadata fields that start with @
            metadata_keys = [k for k in doc.keys() if k.startswith("@")]
            for key in metadata_keys:
                doc.pop(key, None)

            hits.append({"score": score, "document": doc})

        return hits

    except Exception as e:
        print(f"Search failed: {e}")
        import traceback

        traceback.print_exc()
        return []
