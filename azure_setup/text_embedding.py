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

from ._utils import logger, get_subscription_id


def create_openai_resource(cognitive_client, rg_name, openai_name, location):
    try:
        resource = cognitive_client.accounts.begin_create(
            rg_name,
            openai_name,
            {
                "location": location,
                "kind": "OpenAI",
                "sku": {"name": "S0"},
                "properties": {
                    "customSubDomainName": openai_name.lower(),
                    "publicNetworkAccess": "Enabled",
                },
            },
        ).result()
        logger.info(f"Azure OpenAI resource '{openai_name}' created in RG '{rg_name}'.")
        return resource
    except ResourceExistsError:
        logger.warning(f"Azure OpenAI resource '{openai_name}' already exists.")
    except HttpResponseError as e:
        logger.error(f"HTTP error creating Azure OpenAI resource: {e.message}")
        sys.exit(1)


def deploy_embedding_model(
    cognitive_client, rg_name, openai_name, model_name, deployment_name
):
    try:
        deployment = cognitive_client.deployments.begin_create_or_update(
            rg_name,
            openai_name,
            deployment_name,
            {
                "properties": {
                    "model": {"format": "OpenAI", "name": model_name, "version": "1"}
                },
                "sku": {"name": "Standard", "capacity": 1},
            },
        ).result()

        logger.info(f"Model '{model_name}' deployed as '{deployment_name}'.")

        return deployment

    except ResourceExistsError:
        logger.warning(f"Deployment '{deployment_name}' already exists.")
    except HttpResponseError as e:
        logger.error(f"HTTP error deploying model: {e.message}")
        sys.exit(1)


def delete_embedding_deployment(
    cognitive_client, rg_name, openai_name, deployment_name
):
    try:
        cognitive_client.deployments.begin_delete(
            rg_name, openai_name, deployment_name
        ).result()
        logger.info(f"Deployment '{deployment_name}' deleted.")
    except ResourceNotFoundError:
        logger.warning(f"Deployment '{deployment_name}' does not exist.")
    except HttpResponseError as e:
        logger.error(f"HTTP error deleting deployment: {e.message}")
        sys.exit(1)


def delete_openai_resource(cognitive_client, rg_name, openai_name):
    try:
        cognitive_client.accounts.begin_delete(rg_name, openai_name).result()
        logger.info(f"Azure OpenAI resource '{openai_name}' deleted.")
    except ResourceNotFoundError:
        logger.warning(f"Azure OpenAI resource '{openai_name}' does not exist.")
    except HttpResponseError as e:
        logger.error(f"HTTP error deleting Azure OpenAI resource: {e.message}")
        sys.exit(1)


def main():
    try:
        credential = DefaultAzureCredential()
        subscription_id = get_subscription_id(credential)
        cognitive_client = CognitiveServicesManagementClient(
            credential, subscription_id
        )

        if DELETE:
            delete_embedding_deployment(
                cognitive_client, RG_NAME, OPENAI_NAME, EMBEDDING_DEPLOYMENT_NAME
            )
            delete_openai_resource(cognitive_client, RG_NAME, OPENAI_NAME)
        else:
            create_openai_resource(cognitive_client, RG_NAME, OPENAI_NAME, LOCATION)
            deploy_embedding_model(
                cognitive_client,
                RG_NAME,
                OPENAI_NAME,
                EMBEDDING_MODEL_NAME,
                EMBEDDING_DEPLOYMENT_NAME,
            )

        logger.info("Operation completed successfully.")

    except AuthenticationRequiredError as e:
        logger.error(f"Authentication error: {e.message}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
