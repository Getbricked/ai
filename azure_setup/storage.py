import sys
from ._utils import logger
from azure.core.exceptions import ResourceExistsError
from azure.mgmt.storage.models import StorageAccountCreateParameters, Sku, Kind
from azure.core.exceptions import ResourceNotFoundError


def create_storage_account(storage_client, rg_name, storage_name, location):
    """Creates a storage account in the specified resource group."""
    try:
        logger.info(f"Attempting to create storage account '{storage_name}'...")

        storage_params = StorageAccountCreateParameters(
            sku=Sku(name="Standard_LRS"), kind=Kind.STORAGE_V2, location=location
        )

        # The creation process is a long-running operation, so we use 'begin_create'
        poller = storage_client.storage_accounts.begin_create(
            rg_name, storage_name, storage_params
        )

        # Wait for the operation to complete
        account_result = poller.result()
        logger.info(f"Storage account '{account_result.name}' created successfully.")
        return account_result

    except ResourceExistsError:
        logger.warning(f"Storage account '{storage_name}' already exists.")
    except Exception as e:
        logger.error(f"Error creating storage account '{storage_name}': {e}")
        sys.exit(1)


def delete_storage_account(storage_client, rg_name, storage_name):
    """Deletes a storage account in the specified resource group."""
    try:
        logger.info(f"Attempting to delete storage account '{storage_name}'...")
        poller = storage_client.storage_accounts.delete(rg_name, storage_name)
        if poller is not None:
            poller.result()
        logger.info(f"Storage account '{storage_name}' deleted successfully.")
    except ResourceNotFoundError:
        logger.warning(f"Storage account '{storage_name}' not found.")
    except Exception as e:
        logger.error(f"Error deleting storage account '{storage_name}': {e}")
        sys.exit(1)
