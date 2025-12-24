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
    GPT_MODEL_NAME,
    GPT_DEPLOYMENT_NAME,
    SEARCH_NAME,
    INDEX_NAME,
    STORAGE_RG_NAME,
    STORAGE_NAME,
)

from _utils import get_subscription_id, get_search_admin_key, logger
from azure_setup.openai_service import (
    create_openai_resource,
    deploy_model,
)

from azure_setup.resource_group import create_resource_group

from azure_setup.search_service import (
    create_search_service,
    create_search_index,
)

from azure_setup.storage import create_storage_account


def deploy():
    credential = DefaultAzureCredential()
    subscription_id = get_subscription_id(credential)

    resource_client = ResourceManagementClient(credential, subscription_id)
    cognitive_client = CognitiveServicesManagementClient(credential, subscription_id)
    search_client = SearchManagementClient(credential, subscription_id)
    storage_client = StorageManagementClient(credential, subscription_id)

    # Resource group for OpenAI and Search
    create_resource_group(resource_client, RG_NAME, LOCATION)

    # Resource group for Storage
    create_resource_group(resource_client, STORAGE_RG_NAME, LOCATION)
    create_storage_account(
        storage_client,
        STORAGE_RG_NAME,
        STORAGE_NAME,
        LOCATION,
    )

    logger.info("Resource group created.")

    try:
        create_openai_resource(cognitive_client, RG_NAME, OPENAI_NAME, LOCATION)

        # Text Embedding model deployment
        deploy_model(
            cognitive_client,
            RG_NAME,
            OPENAI_NAME,
            EMBEDDING_MODEL_NAME,
            EMBEDDING_DEPLOYMENT_NAME,
            version="1",
            capacity=350,  # Max
        )

        # GPT model deployment
        deploy_model(
            cognitive_client,
            RG_NAME,
            OPENAI_NAME,
            GPT_MODEL_NAME,
            GPT_DEPLOYMENT_NAME,
            version="2024-07-18",
            capacity=200,  # Max
        )

        logger.info("Embedding model deployed successfully.")

        create_search_service(search_client, RG_NAME, SEARCH_NAME, LOCATION)
        admin_key = get_search_admin_key(
            credential, subscription_id, RG_NAME, SEARCH_NAME
        )
        create_search_index(admin_key, SEARCH_NAME, INDEX_NAME)

        logger.info("Search service and index created successfully.")

    except AuthenticationRequiredError as e:
        logger.error(f"Authentication error: {e.message}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    deploy()
