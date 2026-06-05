from azure.storage.blob import BlobServiceClient
from _utils import (
    get_blob_service_connection_string,
    get_azure_openai_credentials,
    get_subscription_id,
)
from _config import CONTAINER_NAME, STORAGE_NAME, STORAGE_RG_NAME, RG_NAME, OPENAI_NAME
from azure.identity import DefaultAzureCredential
import functools


@functools.lru_cache(maxsize=1)
def _get_credential():
    return DefaultAzureCredential()


@functools.lru_cache(maxsize=1)
def _get_subscription_id():
    return get_subscription_id(_get_credential())


@functools.lru_cache(maxsize=1)
def _get_embed_credentials():
    return get_azure_openai_credentials(_get_subscription_id(), RG_NAME, OPENAI_NAME)


@functools.lru_cache(maxsize=1)
def _get_blob_connection_string():
    return get_blob_service_connection_string(
        _get_credential(), _get_subscription_id(), STORAGE_RG_NAME, STORAGE_NAME
    )


@functools.lru_cache(maxsize=1)
def _get_container_client():
    client = BlobServiceClient.from_connection_string(_get_blob_connection_string())
    return client.get_container_client(CONTAINER_NAME)


def __getattr__(name):
    if name == "credential":
        return _get_credential()
    if name == "subscription_id":
        return _get_subscription_id()
    if name == "embed_endpoint":
        return _get_embed_credentials()[0]
    if name == "embed_api_key":
        return _get_embed_credentials()[1]
    if name == "blob_connection_string":
        return _get_blob_connection_string()
    if name == "container_client":
        return _get_container_client()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
