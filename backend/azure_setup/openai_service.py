import sys
from azure.core.exceptions import (
    ResourceExistsError,
    ResourceNotFoundError,
    HttpResponseError,
)

from _utils import logger


def create_openai_resource(cognitive_client, rg_name, openai_name, location):
    """
    Create an Azure OpenAI resource.

    Args:
        cognitive_client: Azure Cognitive Services client
        rg_name: Resource group name
        openai_name: OpenAI resource name
        location: Azure region location
    """
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


def deploy_model(
    cognitive_client,
    rg_name,
    openai_name,
    model_name,
    deployment_name,
    version="1",
    capacity=1,
):
    """
    Deploy a model to Azure OpenAI service.

    Args:
        cognitive_client: Azure Cognitive Services client
        rg_name: Resource group name
        openai_name: OpenAI resource name
        model_name: Model name (e.g., 'text-embedding-3-small', 'gpt-4o-mini')
        deployment_name: Name for the deployment
        version: Model version (default "1" for embeddings, use "2024-07-18" for gpt-4o-mini)
        capacity: Capacity in thousands of tokens per minute (default: 1)
    """
    try:
        deployment = cognitive_client.deployments.begin_create_or_update(
            rg_name,
            openai_name,
            deployment_name,
            {
                "properties": {
                    "model": {
                        "format": "OpenAI",
                        "name": model_name,
                        "version": version,
                    }
                },
                "sku": {"name": "Standard", "capacity": capacity},
            },
        ).result()

        logger.info(
            f"Model '{model_name}' (version {version}) deployed as '{deployment_name}'."
        )

        return deployment

    except ResourceExistsError:
        logger.warning(f"Deployment '{deployment_name}' already exists.")
    except HttpResponseError as e:
        logger.error(f"HTTP error deploying model: {e.message}")
        sys.exit(1)


def delete_deployment(cognitive_client, rg_name, openai_name, deployment_name):
    """
    Delete a deployment from Azure OpenAI service.

    Args:
        cognitive_client: Azure Cognitive Services client
        rg_name: Resource group name
        openai_name: OpenAI resource name
        deployment_name: Name of the deployment to delete
    """
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
    """
    Delete an Azure OpenAI resource.

    Args:
        cognitive_client: Azure Cognitive Services client
        rg_name: Resource group name
        openai_name: OpenAI resource name
    """
    try:
        cognitive_client.accounts.begin_delete(rg_name, openai_name).result()
        logger.info(f"Azure OpenAI resource '{openai_name}' deleted.")
    except ResourceNotFoundError:
        logger.warning(f"Azure OpenAI resource '{openai_name}' does not exist.")
    except HttpResponseError as e:
        logger.error(f"HTTP error deleting Azure OpenAI resource: {e.message}")
        sys.exit(1)


def purge_openai_resource(cognitive_client, rg_name, openai_name, location):
    """
    Purge a soft-deleted Azure OpenAI resource.

    Args:
        cognitive_client: Azure Cognitive Services client
        rg_name: Resource group name
        openai_name: OpenAI resource name
        location: Azure region location
    """
    logger.info(
        f"Attempting to purge resource '{openai_name}' in location '{location}'..."
    )
    try:
        cognitive_client.deleted_accounts.begin_purge(
            location, rg_name, openai_name
        ).result()
        logger.info(
            f"Successfully purged Azure OpenAI resource '{openai_name}' from RG '{rg_name}'."
        )
    except ResourceNotFoundError:
        logger.warning(
            f"Could not purge resource '{openai_name}'. A deleted resource with that name was not found in location '{location}'."
        )
    except HttpResponseError as e:
        logger.error(f"HTTP error purging Azure OpenAI resource: {e.message}")
        sys.exit(1)
