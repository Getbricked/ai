from azure.storage.blob import BlobServiceClient
from ._utils import get_blob_service_connection_string, get_azure_openai_credentials
from _config import CONTAINER_NAME, STORAGE_NAME, STORAGE_RG_NAME, RG_NAME, OPENAI_NAME
from azure_setup._utils import get_subscription_id
from azure.identity import DefaultAzureCredential


credential = DefaultAzureCredential()
subscription_id = get_subscription_id(credential)
endpoint, api_key = get_azure_openai_credentials(subscription_id, RG_NAME, OPENAI_NAME)
print(endpoint)
print(api_key)

# Initialize Blob Storage client
blob_connection_string = get_blob_service_connection_string(
    credential, subscription_id, STORAGE_RG_NAME, STORAGE_NAME
)
blob_service_client = BlobServiceClient.from_connection_string(blob_connection_string)
container_client = blob_service_client.get_container_client(CONTAINER_NAME)
