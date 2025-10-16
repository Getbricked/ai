import sys
from azure.core.exceptions import ResourceNotFoundError
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.identity import DefaultAzureCredential
from openai import OpenAIClient
from azure.core.credentials import AzureKeyCredential
from azure_setup._utils import logger


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


def get_openai_embedding(text, embedding_model, endpoint, api_key):

    if not endpoint or not api_key:
        logger.error("Failed to retrieve Azure OpenAI credentials.")
        return None

    client = OpenAIClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(api_key),
    )
    embedding = (
        client.embeddings.create(model=embedding_model, input=text).data[0].embedding
    )
    return embedding
