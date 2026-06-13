import sys
import logging
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.search import SearchManagementClient
from azure.core.exceptions import ResourceNotFoundError
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.identity import DefaultAzureCredential
from openai import AzureOpenAI, AsyncAzureOpenAI
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
        key_list = keys.keys_property if hasattr(keys, 'keys_property') else keys.keys
        if not key_list:
            logger.error(f"No keys found for storage account '{storage_account_name}'.")
            sys.exit(1)
        account_key = key_list[0].value
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
        logger.info("Authenticating...")
        credential = DefaultAzureCredential()

        cognitiveservices_client = CognitiveServicesManagementClient(
            credential, subscription_id
        )

        # 1. Get the account properties to retrieve the endpoint
        logger.info("Fetching account details for '%s'...", openai_name)
        account = cognitiveservices_client.accounts.get(
            resource_group_name=rg_name, account_name=openai_name
        )
        endpoint = account.properties.endpoint
        logger.info("Successfully retrieved endpoint.")

        # 2. Get the account keys
        logger.info("Fetching keys for '%s'...", openai_name)
        keys = cognitiveservices_client.accounts.list_keys(
            resource_group_name=rg_name, account_name=openai_name
        )
        # We'll return the first key (key1)
        key1 = keys.key1
        logger.info("Successfully retrieved keys.")

        return endpoint, key1

    except Exception as e:
        logger.error("An error occurred: %s", e)
        logger.error(
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


def get_openai_embeddings_batch(
    texts, embedding_name, endpoint, api_key, max_batch_size=50
):
    """Fetch embeddings for a list of texts in batches to reduce round-trips."""

    if not endpoint or not api_key:
        logger.error("Failed to retrieve Azure OpenAI credentials.")
        return []

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version="2023-05-15",
    )

    embeddings = []
    for i in range(0, len(texts), max_batch_size):
        chunk = texts[i : i + max_batch_size]
        try:
            response = client.embeddings.create(model=embedding_name, input=chunk)
            # Ensure order matches input order
            ordered = sorted(response.data, key=lambda x: x.index)
            embeddings.extend([item.embedding for item in ordered])
        except Exception as exc:  # noqa: BLE001
            logger.error("Batch embedding request failed: %s", exc)
            # Pad failures with None to keep alignment
            embeddings.extend([None] * len(chunk))

    return embeddings


def get_openai_completion(messages, model_name, endpoint, api_key):
    if not endpoint or not api_key:
        logger.error("Failed to retrieve Azure OpenAI credentials.")
        return None

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version="2024-02-15-preview",
    )

    response = client.chat.completions.create(model=model_name, messages=messages)
    return response.choices[0].message.content


async def get_openai_embedding_async(text, embedding_name, endpoint, api_key):
    if not endpoint or not api_key:
        logger.error("Failed to retrieve Azure OpenAI credentials.")
        return None

    client = AsyncAzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version="2023-05-15",
    )

    embedding = (await client.embeddings.create(model=embedding_name, input=text)).data[0].embedding
    return embedding


async def get_openai_completion_async(messages, model_name, endpoint, api_key):
    if not endpoint or not api_key:
        logger.error("Failed to retrieve Azure OpenAI credentials.")
        return None

    client = AsyncAzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version="2024-02-15-preview",
    )

    response = await client.chat.completions.create(model=model_name, messages=messages)
    return response.choices[0].message.content
