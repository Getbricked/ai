import logging
import sys
import argparse
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.subscription import SubscriptionClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

from config import LOCATION, RG_NAME, DELETE

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_subscription_id(credential):
    try:
        subcription_client = SubscriptionClient(credential)
        subscriptions = list(subcription_client.subscriptions.list())
        if not subscriptions:
            logger.error("No subscriptions found for the authenticated account.")
            sys.exit(1)
        subscription_id = subscriptions[0].subscription_id
        logger.info(f"Using subscription ID: {subscription_id}")
        return subscription_id

    except Exception as e:
        logger.error(f"Error retrieving subscription ID: {e}")
        sys.exit(1)


def create_resource_group(resource_client, rg_name, location):
    try:
        rg_result = resource_client.resource_groups.create_or_update(
            rg_name, {"location": location}
        )
        logger.info(f"Resource group '{rg_name}' created in location '{location}'.")
        return rg_result
    except ResourceExistsError:
        logger.warning(f"Resource group '{rg_name}' already exists.")
    except Exception as e:
        logger.error(f"Error creating resource group '{rg_name}': {e}")
        sys.exit(1)


def delete_resource_group(resource_client, rg_name):
    try:
        delete_async_operation = resource_client.resource_groups.begin_delete(rg_name)
        delete_async_operation.result()
        logger.info(f"Resource group '{rg_name}' deleted.")
    except ResourceNotFoundError:
        logger.warning(f"Resource group '{rg_name}' does not exist.")
    except Exception as e:
        logger.error(f"Error deleting resource group '{rg_name}': {e}")
        sys.exit(1)


def main():
    # Getting credential
    credential = DefaultAzureCredential()
    subscription_id = get_subscription_id(credential)
    resource_client = ResourceManagementClient(credential, subscription_id)

    if DELETE:
        delete_resource_group(resource_client, RG_NAME)
    else:
        create_resource_group(resource_client, RG_NAME, LOCATION)

    logger.info("Operation completed successfully.")


if __name__ == "__main__":
    main()
