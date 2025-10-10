import sys
from azure.core.exceptions import (
    ResourceExistsError,
    ResourceNotFoundError,
    HttpResponseError,
)

from ._utils import logger


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


def purge_openai_resource(cognitive_client, rg_name, openai_name, location):
    """Purges a soft-deleted Azure OpenAI resource."""
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
