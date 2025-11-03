from azure.search.documents import SearchClient
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential
from _credentials import (
    credential,
    subscription_id,
    endpoint,
    api_key,
)
from _config import RG_NAME, SEARCH_NAME, INDEX_NAME
from _utils import get_search_admin_key


def run_search_query():
    """Connects to Azure Search using utils and runs a simple query."""

    print(
        "Authenticating with Azure CLI credentials (make sure you've run 'az login')..."
    )

    try:
        auth_credential = DefaultAzureCredential()

        print(f"Fetching admin key for search service '{SEARCH_NAME}'...")
        admin_key = get_search_admin_key(
            auth_credential, subscription_id, RG_NAME, SEARCH_NAME
        )
        print("Successfully retrieved search admin key.")

        search_credential = AzureKeyCredential(admin_key)

        search_client = SearchClient(
            endpoint=endpoint,
            index_name=INDEX_NAME,
            credential=search_credential,
        )

        search_text = "test file"  # You can change this to any query

        print(f"\nSearching for: '{search_text}' in index '{INDEX_NAME}'...")

        results = search_client.search(
            search_text=search_text, include_total_count=True
        )

        print(f"Found {results.get_count()} total results.")

        # 7. Process and print the results
        print("\n--- Search Results ---")
        for document in results:
            # Each 'document' is a dictionary representing one item from your index
            print(document)
        print("------------------------")
        print("Search query completed.")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
        print(
            "Please check your configuration values (RG_NAME, SEARCH_NAME, INDEX_NAME)"
        )
        print(
            "Also ensure you are logged in via 'az login' with sufficient permissions to read subscription details and search service keys."
        )
