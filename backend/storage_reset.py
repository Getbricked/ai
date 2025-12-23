from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.identity import DefaultAzureCredential
from _utils import get_subscription_id, logger
from azure_setup.storage import delete_storage_account
from azure_setup.resource_group import delete_resource_group
from _config import STORAGE_RG_NAME, STORAGE_NAME
from azure.identity import AuthenticationRequiredError
import sys


def storage_reset():
    credential = DefaultAzureCredential()
    subscription_id = get_subscription_id(credential)
    storage_client = StorageManagementClient(credential, subscription_id)
    resource_client = ResourceManagementClient(credential, subscription_id)

    try:
        logger.info("Deleting storage blob...")
        # Storage cleanup (incase need to reset storage)
        delete_storage_account(storage_client, STORAGE_RG_NAME, STORAGE_NAME)
        delete_resource_group(resource_client, STORAGE_RG_NAME)

        logger.info("All storage resources deleted.")

    except AuthenticationRequiredError as e:
        logger.error(f"Authentication error: {e.message}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    storage_reset()
