import sys
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.search import SearchManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.identity import AuthenticationRequiredError
from _config import (
    RG_NAME,
    LOCATION,
    OPENAI_NAME,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_DEPLOYMENT_NAME,
    SEARCH_NAME,
    INDEX_NAME,
    STORAGE_RG_NAME,
    STORAGE_NAME,
)

from _utils import get_subscription_id, logger
from azure_setup.text_embedding import (
    delete_embedding_deployment,
    delete_openai_resource,
    purge_openai_resource,
)

from azure_setup.resource_group import delete_resource_group

from azure_setup.search_service import (
    delete_search_service,
)

from azure_setup.storage import delete_storage_account


def delete():
    credential = DefaultAzureCredential()
    subscription_id = get_subscription_id(credential)

    resource_client = ResourceManagementClient(credential, subscription_id)
    cognitive_client = CognitiveServicesManagementClient(credential, subscription_id)
    search_client = SearchManagementClient(credential, subscription_id)
    storage_client = StorageManagementClient(credential, subscription_id)

    try:
        logger.info("DELETE flag is set. Deleting resources...")

        delete_embedding_deployment(
            cognitive_client, RG_NAME, OPENAI_NAME, EMBEDDING_DEPLOYMENT_NAME
        )

        delete_openai_resource(cognitive_client, RG_NAME, OPENAI_NAME)
        purge_openai_resource(cognitive_client, RG_NAME, OPENAI_NAME, LOCATION)
        delete_search_service(search_client, RG_NAME, SEARCH_NAME)
        delete_resource_group(resource_client, RG_NAME)

        # Storage cleanup (incase need to reset storage)
        # delete_storage_account(storage_client, STORAGE_RG_NAME, STORAGE_NAME)
        # delete_resource_group(resource_client, STORAGE_RG_NAME)

        logger.info("All resources deleted as per DELETE flag.")

    except AuthenticationRequiredError as e:
        logger.error(f"Authentication error: {e.message}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    delete()
