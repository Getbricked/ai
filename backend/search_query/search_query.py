import logging
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential
import json
from typing import List, Dict, Any, Optional
from azure.search.documents.models import VectorizedQuery  # Change this import

logger = logging.getLogger(__name__)


def load_json_documents_from_blob(
    connection_string: str, container_name: str
) -> List[Dict[str, Any]]:
    """
    Loads JSON documents from Azure Blob Storage.

    Args:
        connection_string: Azure Storage connection string
        container_name: Name of the blob container

    Returns:
        List of document dictionaries
    """
    logger.info("Loading JSON documents from container '%s'...", container_name)
    documents = []

    try:
        blob_service_client = BlobServiceClient.from_connection_string(
            connection_string
        )
        container_client = blob_service_client.get_container_client(container_name)

        blob_list = container_client.list_blobs()
        for blob in blob_list:
            if blob.name.endswith(".json"):
                logger.info("Processing %s...", blob.name)
                blob_client = container_client.get_blob_client(blob)
                blob_data = blob_client.download_blob().readall()

                try:
                    data = json.loads(blob_data)

                    if isinstance(data, list):
                        documents.extend(data)
                    elif isinstance(data, dict):
                        documents.append(data)
                    else:
                        logger.warning(
                            "%s does not contain a valid JSON object or list.", blob.name
                        )

                except json.JSONDecodeError:
                    logger.warning("Could not decode JSON from %s.", blob.name)
                except Exception as e:
                    logger.error("Error processing blob %s: %s", blob.name, e)

        if not documents:
            logger.info("No valid .json documents found in blob container.")
            return []

        logger.info("Loaded %d documents from %s.", len(documents), container_name)
        return documents

    except Exception as e:
        logger.error("Error loading documents from blob: %s", e)
        raise


def map_documents_for_search(
    documents: List[Dict[str, Any]], field_mapping: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    """
    Maps document fields to Azure AI Search index fields.

    Args:
        documents: List of source documents
        field_mapping: Optional custom field mapping.
                      Default maps contentVector -> content_vector

    Returns:
        List of mapped documents ready for upload
    """
    if field_mapping is None:
        field_mapping = {
            "id": "id",
            "content": "content",
            "contentVector": "content_vector",
            "source": "source",
            "category": "category",
        }

    logger.info("Mapping fields and preparing documents for upload...")
    documents_to_upload = []

    for doc in documents:
        try:
            doc_to_upload = {}
            for source_field, target_field in field_mapping.items():
                doc_to_upload[target_field] = doc.get(source_field)

            # Basic validation
            if not all(
                [
                    doc_to_upload.get("id"),
                    doc_to_upload.get("content"),
                    doc_to_upload.get("content_vector"),
                ]
            ):
                logger.warning("Skipping document (missing required fields): %s", doc.get("id"))
                continue

            documents_to_upload.append(doc_to_upload)
        except Exception as e:
            logger.error("Error mapping document %s: %s", doc.get("id"), e)

    return documents_to_upload


def upload_documents_to_search(
    search_client: SearchClient, documents: List[Dict[str, Any]]
) -> bool:
    """
    Uploads documents to Azure AI Search index.

    Args:
        search_client: Initialized SearchClient instance
        documents: List of documents to upload

    Returns:
        True if all documents uploaded successfully, False otherwise
    """
    if not documents:
        logger.info("No documents to upload.")
        return False

    max_batch_size = 100
    logger.info(
        "Uploading %d documents to index in batches of %d...", len(documents), max_batch_size
    )
    try:
        all_success = True
        total_uploaded = 0

        for start in range(0, len(documents), max_batch_size):
            batch = documents[start : start + max_batch_size]
            batch_number = start // max_batch_size + 1
            total_batches = (len(documents) + max_batch_size - 1) // max_batch_size
            logger.info(
                "Uploading batch %d/%d (%d documents)...",
                batch_number, total_batches, len(batch),
            )

            result = search_client.upload_documents(documents=batch)
            batch_success = True

            for r in result:
                if not r.succeeded:
                    batch_success = False
                    logger.warning("  - Document %s: %s", r.key, r.error_message)

            if batch_success:
                total_uploaded += len(batch)
            else:
                all_success = False

        if all_success:
            logger.info("Successfully uploaded all %d documents.", total_uploaded)
        else:
            logger.info("Uploaded %d documents with some failures.", total_uploaded)

        return all_success

    except Exception as e:
        logger.error("Error uploading documents: %s", e)
        return False


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
        logger.error("Search failed: %s", e)
        import traceback

        traceback.print_exc()
        return []


async def search_index_async(
    search_client: SearchClient,
    query_text: Optional[str] = None,
    vector: Optional[List[float]] = None,
    vector_field: str = "content_vector",
    top_k: int = 10,
    filter: Optional[str] = None,
    select: Optional[List[str]] = None,
    semantic_configuration_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
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
            vq = VectorizedQuery(
                vector=vector,
                k_nearest_neighbors=top_k,
                fields=vector_field,
                kind="vector",
            )
            search_text = query_text if query_text is not None else None
            results = await search_client.search(
                search_text=search_text, vector_queries=[vq], **search_kwargs
            )
        else:
            results = await search_client.search(search_text=query_text, **search_kwargs)

        hits: List[Dict[str, Any]] = []
        async for r in results:
            doc = dict(r)
            score = doc.pop("@search.score", None)
            metadata_keys = [k for k in doc.keys() if k.startswith("@")]
            for key in metadata_keys:
                doc.pop(key, None)
            hits.append({"score": score, "document": doc})

        return hits

    except Exception as e:
        logger.error("Search failed: %s", e)
        import traceback

        traceback.print_exc()
        return []
