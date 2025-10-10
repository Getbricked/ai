import sys
from azure.core.exceptions import ResourceNotFoundError
from azure.mgmt.storage import StorageManagementClient
from azure_setup._utils import logger


def get_blob_service_connection_string(
    credential, subscription_id, rg_name, storage_account_name
):
    try:
        storage_client = StorageManagementClient(credential, subscription_id)
        keys = storage_client.storage_accounts.list_keys(rg_name, storage_account_name)
        if not keys.keys:
            logger.error(f"No keys found for storage account '{storage_account_name}'.")
            sys.exit(1)
        account_key = keys.keys[0].value
        connection_string = (
            f"DefaultEndpointsProtocol=https;"
            f"AccountName={storage_account_name};"
            f"AccountKey={account_key};"
            f"EndpointSuffix=core.windows.net"
        )
        logger.info(
            f"Retrieved connection string for storage account '{storage_account_name}'."
        )
        return connection_string
    except ResourceNotFoundError:
        logger.error(
            f"Storage account '{storage_account_name}' not found in resource group '{rg_name}'."
        )
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error retrieving blob service connection string: {e}")
        sys.exit(1)
