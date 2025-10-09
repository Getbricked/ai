import sys
import logging
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.search import SearchManagementClient
from azure.core.exceptions import ResourceNotFoundError

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_subscription_id(credential):
    try:
        subscription_client = SubscriptionClient(credential)
        subscriptions = list(subscription_client.subscriptions.list())
        if not subscriptions:
            logger.error("No subscriptions found for the authenticated account.")
            sys.exit(1)
        subscription_id = subscriptions[0].subscription_id
        logger.info(f"Using subscription ID: {subscription_id}")
        return subscription_id

    except Exception as e:
        logger.error(f"Error retrieving subscription ID: {e}")
        sys.exit(1)


def get_search_admin_key(credential, subscription_id, rg_name, search_name):
    try:
        search_client = SearchManagementClient(credential, subscription_id)
        keys = search_client.admin_keys.get(rg_name, search_name)
        return keys.primary_key
    except ResourceNotFoundError:
        logger.error(
            f"Search service '{search_name}' not found in resource group '{rg_name}'."
        )
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error retrieving search admin key: {e}")
        sys.exit(1)
