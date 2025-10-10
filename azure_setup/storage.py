import sys
from ._utils import logger
from azure.core.exceptions import ResourceExistsError
from azure.mgmt.storage.models import StorageAccountCreateParameters, Sku, Kind
from azure.core.exceptions import ResourceNotFoundError


def create_resource_group(resource_client, rg_name, location):
    """Creates a resource group."""
    try:
        logger.info(f"Attempting to create resource group '{rg_name}'...")
        rg_result = resource_client.resource_groups.create_or_update(
            rg_name, {"location": location}
        )
        logger.info(f"Resource group '{rg_name}' created in location '{location}'.")
        return rg_result
    except ResourceExistsError:
        logger.warning(f"Resource group '{rg_name}' already exists.")
        # If it already exists, we can still proceed.
        return resource_client.resource_groups.get(rg_name)
    except Exception as e:
        logger.error(f"Error creating resource group '{rg_name}': {e}")
        sys.exit(1)


def create_storage_account(storage_client, rg_name, account_name, location):
    """Creates a storage account in the specified resource group."""
    try:
        logger.info(f"Attempting to create storage account '{account_name}'...")

        # Define the parameters for the storage account
        # Standard_LRS is the most common and is eligible for the free tier.
        # StorageV2 is the general-purpose account type.
        storage_params = StorageAccountCreateParameters(
            sku=Sku(name="Standard_LRS"), kind=Kind.STORAGE_V2, location=location
        )

        # The creation process is a long-running operation, so we use 'begin_create'
        poller = storage_client.storage_accounts.begin_create(
            rg_name, account_name, storage_params
        )

        # Wait for the operation to complete
        account_result = poller.result()
        logger.info(f"Storage account '{account_result.name}' created successfully.")
        return account_result

    except ResourceExistsError:
        logger.warning(f"Storage account '{account_name}' already exists.")
    except Exception as e:
        logger.error(f"Error creating storage account '{account_name}': {e}")
        sys.exit(1)


def delete_resource_group(resource_client, rg_name):
    """Deletes a resource group and all resources within it."""
    try:
        logger.info(f"Attempting to delete resource group '{rg_name}'...")
        # Deleting a resource group is a long-running operation
        delete_poller = resource_client.resource_groups.begin_delete(rg_name)
        delete_poller.result()
        logger.info(f"Resource group '{rg_name}' and all its resources deleted.")
    except ResourceNotFoundError:
        logger.warning(f"Resource group '{rg_name}' does not exist.")
    except Exception as e:
        logger.error(f"Error deleting resource group '{rg_name}': {e}")
        sys.exit(1)
