import sys
import requests
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SemanticSearch,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
)
from azure.core.exceptions import (
    ResourceExistsError,
    ResourceNotFoundError,
    HttpResponseError,
)
from _utils import logger


def create_search_service(search_client, rg_name, search_name, location):
    """
    Create or update an Azure AI Search service.

    Args:
        search_client: Azure Search service client
        rg_name: Resource group name
        search_name: Search service name
        location: Azure region location
    """
    import random

    def _try_create(name, is_retry=False):
        try:
            logger.info(f"Creating or updating search service '{name}'...")
            poller = search_client.services.begin_create_or_update(
                rg_name,
                name,
                {
                    "location": location,
                    "sku": {"name": "free"},
                    "properties": {
                        "replicaCount": 1,
                        "partitionCount": 1,
                        "hostingMode": "default",
                    },
                },
            )
            service = poller.result()
            logger.info(f"Search service '{name}' is ready.")
            return service
        except ResourceExistsError:
            if is_retry:
                logger.warning(f"Search service '{name}' already exists. Retrieving it.")
                return search_client.services.get(rg_name, name)
            return None
        except HttpResponseError as e:
            logger.error(f"HTTP error creating search service: {e.message}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during service creation: {e}")
            return None

    result = _try_create(search_name)
    if result is None:
        suffix = random.randint(1000, 9999)
        alt_name = f"{search_name}-{suffix}"
        logger.warning(f"Search name '{search_name}' unavailable, trying '{alt_name}'...")
        result = _try_create(alt_name, is_retry=True)
    return result


def create_search_index(admin_key: str, search_name: str, index_name: str):
    """
    Create a semantic-enabled search index with vector search support.

    Vector search is the primary search method, with semantic ranking as optional reranking.

    Args:
        admin_key: Azure Search admin API key
        search_name: Search service name
        index_name: Name of the index to create
    """
    logger.info("Attempting to create semantic index '%s'...", index_name)

    endpoint = f"https://{search_name}.search.windows.net"
    credential = AzureKeyCredential(admin_key)
    index_client = SearchIndexClient(endpoint=endpoint, credential=credential)

    # Define the vector search configuration - primary search method
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="hnsw-algorithm-config",
                parameters={
                    "m": 4,
                    "efConstruction": 400,
                    "efSearch": 500,
                    "metric": "cosine",
                },
            )
        ],
        profiles=[
            VectorSearchProfile(
                name="vector-profile",
                algorithm_configuration_name="hnsw-algorithm-config",
            )
        ],
    )

    fields = [
        SearchField(name="id", type=SearchFieldDataType.String, key=True),
        SearchField(
            name="content",
            type=SearchFieldDataType.String,
            searchable=True,
            retrievable=True,
        ),
        SearchField(
            name="category",
            type=SearchFieldDataType.String,
            searchable=True,
            filterable=True,
            facetable=True,
        ),
        SearchField(
            name="source",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
            sortable=True,
        ),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            vector_search_dimensions=1536,
            vector_search_profile_name="vector-profile",
            searchable=True,
        ),
    ]

    # Define the semantic search configuration - for reranking vector results
    semantic_config_name = "cybersecurity-semantic-config"
    semantic_search = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name=semantic_config_name,
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=None,  # No title field in your schema
                    content_fields=[SemanticField(field_name="content")],
                    keywords_fields=[SemanticField(field_name="category")],
                ),
            )
        ]
    )

    # Create the index with both vector and semantic search
    index = SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=vector_search,  # Primary: vector search
        semantic_search=semantic_search,  # Secondary: semantic reranking
    )

    try:
        result = index_client.create_or_update_index(index)
        logger.info("Semantic index '%s' created/updated successfully!", result.name)
        logger.info("  - Primary search: Vector search (HNSW)")
        logger.info("  - Reranking: Semantic search ('%s')", semantic_config_name)
        return semantic_config_name
    except Exception as e:
        logger.error("An error occurred: %s", e)
        return None


def delete_search_service(search_client, rg_name, search_name):
    """
    Delete an Azure AI Search service.

    Args:
        search_client: Azure Search service client
        rg_name: Resource group name
        search_name: Search service name
    """
    try:
        logger.info(f"Deleting search service '{search_name}'...")
        search_client.services.delete(rg_name, search_name)
        logger.info(f"Search service '{search_name}' deleted successfully.")
    except ResourceNotFoundError:
        logger.warning(f"Search service '{search_name}' not found; nothing to delete.")
    except HttpResponseError as e:
        logger.error(f"HTTP error deleting search service: {e.message}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error deleting search service: {e}")
        sys.exit(1)
