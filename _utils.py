import sys
import logging
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.search import SearchManagementClient
from azure.core.exceptions import ResourceNotFoundError
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.identity import DefaultAzureCredential
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential

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


def get_blob_service_connection_string(
    credential, subscription_id, rg_name, storage_account_name
):
    try:
        storage_client = StorageManagementClient(credential, subscription_id)
        keys = storage_client.storage_accounts.list_keys(rg_name, storage_account_name)
        if not keys.keys:
            logger.error(f"No keys found for storage account '{storage_account_name}'.")
            sys.exit(1)
        account_key = keys.keys[0].value
        connection_string = (
            f"DefaultEndpointsProtocol=https;"
            f"AccountName={storage_account_name};"
            f"AccountKey={account_key};"
            f"EndpointSuffix=core.windows.net"
        )
        logger.info(
            f"Retrieved connection string for storage account '{storage_account_name}'."
        )
        return connection_string
    except ResourceNotFoundError:
        logger.error(
            f"Storage account '{storage_account_name}' not found in resource group '{rg_name}'."
        )
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error retrieving blob service connection string: {e}")
        sys.exit(1)


def get_azure_openai_credentials(subscription_id, rg_name, openai_name):
    try:
        print("Authenticating...")
        credential = DefaultAzureCredential()

        cognitiveservices_client = CognitiveServicesManagementClient(
            credential, subscription_id
        )

        # 1. Get the account properties to retrieve the endpoint
        print(f"Fetching account details for '{openai_name}'...")
        account = cognitiveservices_client.accounts.get(
            resource_group_name=rg_name, account_name=openai_name
        )
        endpoint = account.properties.endpoint
        print("Successfully retrieved endpoint.")

        # 2. Get the account keys
        print(f"Fetching keys for '{openai_name}'...")
        keys = cognitiveservices_client.accounts.list_keys(
            resource_group_name=rg_name, account_name=openai_name
        )
        # We'll return the first key (key1)
        key1 = keys.key1
        print("Successfully retrieved keys.")

        return endpoint, key1

    except Exception as e:
        print(f"An error occurred: {e}")
        print(
            "Please ensure you have the correct permissions (e.g., 'Cognitive Services User' or 'Contributor' role) "
            "on the resource group or OpenAI account."
        )
        return None, None


def get_openai_embedding(text, embedding_name, endpoint, api_key):

    if not endpoint or not api_key:
        logger.error("Failed to retrieve Azure OpenAI credentials.")
        return None

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version="2023-05-15",  # Recommended to use a specific API version
    )

    embedding = (
        client.embeddings.create(model=embedding_name, input=text).data[0].embedding
    )
    return embedding
