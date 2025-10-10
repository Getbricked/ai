import sys
import requests
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


def create_search_index(admin_key, search_name, index_name):
    """Creates or updates a search index with vector and semantic configurations."""
    try:
        logger.info(f"Creating or updating search index '{index_name}'...")
        url = f"https://{search_name}.search.windows.net/indexes/{index_name}?api-version=2025-09-01"
        headers = {"Content-Type": "application/json", "api-key": admin_key}
        index_definition = {
            "name": index_name,
            "fields": [
                {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
                {
                    "name": "title",
                    "type": "Edm.String",
                    "searchable": True,
                    "retrievable": True,
                },
                {
                    "name": "filepath",
                    "type": "Edm.String",
                    "searchable": False,
                    "retrievable": True,
                },
                {
                    "name": "content",
                    "type": "Edm.String",
                    "searchable": True,
                    "retrievable": True,
                },
                {
                    "name": "embedding",
                    "type": "Collection(Edm.Single)",
                    "searchable": True,
                    "retrievable": True,
                    "dimensions": 1536,
                    "vectorSearchProfile": "my-vector-profile",
                },
            ],
            "vectorSearch": {
                "profiles": [
                    {"name": "my-vector-profile", "algorithm": "my-hnsw-config"}
                ],
                "algorithms": [{"name": "my-hnsw-config", "kind": "hnsw"}],
            },
            # "semanticSearch": {
            #     "configurations": [
            #         {
            #             "name": "my-semantic-config",
            #             "prioritizedFields": {
            #                 "titleField": {"fieldName": "title"},
            #                 "prioritizedContentFields": [{"fieldName": "content"}],
            #             },
            #         }
            #     ]
            # },
        }
        response = requests.put(url, headers=headers, json=index_definition)

        # Check response status and log appropriately
        if response.status_code == 201:
            logger.info(f"Search index '{index_name}' created successfully.")
        elif response.status_code == 204:
            logger.info(f"Search index '{index_name}' updated successfully.")
        else:
            # This will raise an exception for other error codes
            response.raise_for_status()

    except requests.exceptions.HTTPError as e:
        # Handle 409 Conflict specifically, which means the index exists but differs
        if e.response.status_code == 409:
            logger.warning(
                f"Search index '{index_name}' already exists with a different definition."
            )
        else:
            logger.error(f"HTTP error managing search index: {e.response.text}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred during index management: {e}")
        sys.exit(1)


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
