from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential
import json
from typing import List, Dict, Any, Optional


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
    print(f"Loading JSON documents from container '{container_name}'...")
    documents = []

    try:
        blob_service_client = BlobServiceClient.from_connection_string(
            connection_string
        )
        container_client = blob_service_client.get_container_client(container_name)

        blob_list = container_client.list_blobs()
        for blob in blob_list:
            if blob.name.endswith(".json"):
                print(f"Processing {blob.name}...")
                blob_client = container_client.get_blob_client(blob)
                blob_data = blob_client.download_blob().readall()

                try:
                    data = json.loads(blob_data)

                    if isinstance(data, list):
                        documents.extend(data)
                    elif isinstance(data, dict):
                        documents.append(data)
                    else:
                        print(
                            f"Warning: {blob.name} does not contain a valid JSON object or list."
                        )

                except json.JSONDecodeError:
                    print(f"Warning: Could not decode JSON from {blob.name}.")
                except Exception as e:
                    print(f"Error processing blob {blob.name}: {e}")

        if not documents:
            print("No valid .json documents found in blob container.")
            return []

        print(f"Loaded {len(documents)} documents from {container_name}.")
        return documents

    except Exception as e:
        print(f"Error loading documents from blob: {e}")
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

    print("Mapping fields and preparing documents for upload...")
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
                print(f"Skipping document (missing required fields): {doc.get('id')}")
                continue

            documents_to_upload.append(doc_to_upload)
        except Exception as e:
            print(f"Error mapping document {doc.get('id')}: {e}")

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
        print("No documents to upload.")
        return False

    print(f"Uploading {len(documents)} documents to index...")
    try:
        result = search_client.upload_documents(documents=documents)
        success = all(r.succeeded for r in result)

        if success:
            print(f"Successfully uploaded all {len(documents)} documents.")
        else:
            print("Some documents failed to upload:")
            for r in result:
                if not r.succeeded:
                    print(f"  - Document {r.key}: {r.error_message}")

        return success

    except Exception as e:
        print(f"Error uploading documents: {e}")
        return False


def ingest_documents_from_blob_to_search(
    azure_storage_connection_string: str,
    container_name: str,
    search_endpoint: str,
    search_key: str,
    index_name: str,
    field_mapping: Optional[Dict[str, str]] = None,
) -> bool:
    """
    Complete pipeline to load documents from blob storage and upload to Azure AI Search.

    Args:
        azure_storage_connection_string: Azure Storage connection string
        container_name: Blob container name
        search_endpoint: Azure AI Search endpoint
        search_key: Azure AI Search admin key
        index_name: Name of the search index
        field_mapping: Optional custom field mapping

    Returns:
        True if ingestion completed successfully, False otherwise
    """
    try:
        # 1. Load documents from blob
        documents = load_json_documents_from_blob(
            azure_storage_connection_string, container_name
        )

        if not documents:
            print("No documents loaded. Exiting.")
            return False

        # 2. Map documents
        mapped_documents = map_documents_for_search(documents, field_mapping)

        if not mapped_documents:
            print("No valid documents after mapping. Exiting.")
            return False

        # 3. Upload to search
        search_credential = AzureKeyCredential(search_key)
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=index_name,
            credential=search_credential,
        )

        success = upload_documents_to_search(search_client, mapped_documents)

        print("\n--- Data Ingestion Complete ---")
        return success

    except Exception as e:
        print(f"An error occurred during the ingestion process: {e}")
        return False
