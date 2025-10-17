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
)
from azure.core.exceptions import (
    ResourceExistsError,
    ResourceNotFoundError,
    HttpResponseError,
)
from azure_setup._utils import logger


def create_search_service(search_client, rg_name, search_name, location):
    """Creates or updates an Azure AI Search service."""
    try:
        logger.info(f"Creating or updating search service '{search_name}'...")
        poller = search_client.services.begin_create_or_update(
            rg_name,
            search_name,
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
        logger.info(f"Search service '{search_name}' is ready.")
        return service
    except ResourceExistsError:
        # This case is less likely with begin_create_or_update but handled for safety
        logger.warning(f"Search service '{search_name}' already exists. Retrieving it.")
        return search_client.services.get(rg_name, search_name)
    except HttpResponseError as e:
        logger.error(f"HTTP error creating search service: {e.message}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during service creation: {e}")
        return None


def create_search_index(admin_key: str, search_name: str, index_name: str):
    """
    Creates a semantic-enabled search index for cybersecurity documents.
    """
    print(f"Attempting to create semantic index '{index_name}'...")

    endpoint = f"https://{search_name}.search.windows.net"
    credential = AzureKeyCredential(admin_key)
    index_client = SearchIndexClient(endpoint=endpoint, credential=credential)

    fields = [
        SearchField(name="id", type=SearchFieldDataType.String, key=True),
        SearchField(
            name="title",
            type=SearchFieldDataType.String,
            searchable=True,
            sortable=True,
        ),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
        SearchField(
            name="keywords",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True,
            filterable=True,
            facetable=True,
        ),
        SearchField(
            name="author",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
            sortable=True,
        ),
        SearchField(
            name="publicationDate",
            type=SearchFieldDataType.DateTimeOffset,
            filterable=True,
            sortable=True,
        ),
        SearchField(
            name="documentType",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),
        SearchField(
            name="cve_ids",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True,
            filterable=True,
            facetable=True,
        ),
    ]

    # --- CORRECTED: Define the semantic search configuration ---
    semantic_config_name = "cybersecurity-semantic-config"
    semantic_search = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name=semantic_config_name,
                # This block is now structured correctly
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="title"),
                    prioritized_content_fields=[SemanticField(field_name="content")],
                    prioritized_keywords_fields=[
                        SemanticField(field_name="keywords"),
                        SemanticField(field_name="cve_ids"),
                    ],
                ),
            )
        ]
    )

    # Add the semantic_search object to the index definition
    index = SearchIndex(
        name=index_name,
        fields=fields,
        semantic_search=semantic_search,  # <-- ADD THIS LINE
    )

    try:
        result = index_client.create_or_update_index(
            index
        )  # Use create_or_update for easier iteration
        print(f"Semantic index '{result.name}' created/updated successfully! ✅")
        # Return the config name so we can use it in queries
        return semantic_config_name
    except Exception as e:
        print(f"An error occurred: {e} ❌")
        return None


def delete_search_service(search_client, rg_name, search_name):
    """Deletes the search service."""
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
