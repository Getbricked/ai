import sys
import logging
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.core.exceptions import (
    ResourceExistsError,
    ResourceNotFoundError,
    HttpResponseError,
)
from azure.identity import AuthenticationRequiredError
from azure_setup._config import (
    RG_NAME,
    LOCATION,
    OPENAI_NAME,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_DEPLOYMENT_NAME,
    DELETE,
)

from azure_setup._utils import logger, get_subscription_id
from azure_setup.text_embedding import (
    delete_embedding_deployment,
    delete_openai_resource,
    create_openai_resource,
    deploy_embedding_model,
)

from azure_setup.resource_group import (
    create_resource_group,
    delete_resource_group,
)


def main():
    credential = DefaultAzureCredential()
    subscription_id = get_subscription_id(credential)
    cognitive_client = CognitiveServicesManagementClient(credential, subscription_id)
    resource_client = ResourceManagementClient(credential, subscription_id)

    create_resource_group(resource_client, RG_NAME, LOCATION)

    logger.info("Resource group created.")

    try:
        create_openai_resource(cognitive_client, RG_NAME, OPENAI_NAME, LOCATION)
        deploy_embedding_model(
            cognitive_client,
            RG_NAME,
            OPENAI_NAME,
            EMBEDDING_MODEL_NAME,
            EMBEDDING_DEPLOYMENT_NAME,
        )
        logger.info("Embedding model deployed successfully.")

        if DELETE:
            delete_embedding_deployment(
                cognitive_client, RG_NAME, OPENAI_NAME, EMBEDDING_DEPLOYMENT_NAME
            )
            delete_openai_resource(cognitive_client, RG_NAME, OPENAI_NAME)
            delete_resource_group(resource_client, RG_NAME)
            logger.info("All resources deleted as per DELETE flag.")

    except AuthenticationRequiredError as e:
        logger.error(f"Authentication error: {e.message}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
