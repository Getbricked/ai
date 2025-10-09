import sys
import logging
import requests
from azure.identity import DefaultAzureCredential
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.search import SearchManagementClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.identity import AuthenticationRequiredError
from ._config import RG_NAME, LOCATION, SEARCH_NAME, INDEX_NAME, DELETE

from ._utils import get_subscription_id, logger, get_search_admin_key


def create_search_service(search_client, rg_name, search_name, location):
    try:
        logger.info(
            f"Creating Azure AI Search service '{search_name}' in resource group '{rg_name}'..."
        )
        poller = search_client.services.begin_create_or_update(
            rg_name,
            search_name,
            {
                "location": location,
                "sku": {"name": "free"},
                "replica_count": 1,
                "partition_count": 1,
                "hosting_mode": "default",
            },
        )
        service = poller.result()
        logger.info(f"Search service '{search_name}' created successfully.")
        return service
    except ResourceExistsError:
        logger.warning(f"Search service '{search_name}' already exists.")
        return search_client.services.get(rg_name, search_name)
    except Exception as e:
        logger.error(f"Error creating search service: {e}")
        sys.exit(1)


def create_search_index(admin_key, search_name, index_name):
    try:
        logger.info(
            f"Creating search index '{index_name}' in service '{search_name}'..."
        )

        url = f"https://{search_name}.search.windows.net/indexes?api-version=2024-07-01"

        headers = {
            "Content-Type": "application/json",
            "api-key": admin_key,
        }

        index_definition = {
            "name": index_name,
            "fields": [
                {"name": "id", "type": "Edm.String", "key": True, "searchable": False},
                {
                    "name": "content",
                    "type": "Edm.String",
                    "searchable": True,
                    "filterable": False,
                    "sortable": False,
                },
                {
                    "name": "embedding",
                    "type": "Collection(Edm.Double)",
                    "searchable": True,
                    "retrievable": True,
                },
            ],
        }

        response = requests.put(url, headers=headers, json=index_definition)
        response.raise_for_status()
        logger.info(f"Search index '{index_name}' created successfully.")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 409:
            logger.warning(f"Search index '{index_name}' already exists.")
        else:
            logger.error(f"HTTP error creating search index: {e.response.text}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error creating search index: {e}")
        sys.exit(1)


def delete_search_service(search_client, rg_name, search_name):
    try:
        logger.info(f"Deleting search service '{search_name}'...")
        poller = search_client.services.begin_delete(rg_name, search_name)
        poller.result()
        logger.info(f"Search service '{search_name}' deleted successfully.")
    except ResourceNotFoundError:
        logger.warning(f"Search service '{search_name}' not found.")
    except Exception as e:
        logger.error(f"Error deleting search service: {e}")
        sys.exit(1)


def delete_search_index(admin_key, search_name, index_name):
    try:
        logger.info(f"Deleting search index '{index_name}'...")
        url = f"https://{search_name}.search.windows.net/indexes/{index_name}?api-version=2024-07-01"

        headers = {
            "Content-Type": "application/json",
            "api-key": admin_key,
        }

        response = requests.delete(url, headers=headers)
        if response.status_code == 404:
            logger.warning(f"Search index '{index_name}' not found.")
        else:
            response.raise_for_status()
            logger.info(f"Search index '{index_name}' deleted successfully.")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error deleting search index: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error deleting search index: {e}")
        sys.exit(1)
