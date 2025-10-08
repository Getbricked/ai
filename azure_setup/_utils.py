import sys
import logging
from azure.mgmt.subscription import SubscriptionClient

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
