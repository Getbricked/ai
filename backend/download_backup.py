import os
import json
import sys
from typing import List, Dict, Any, Optional

from _credentials import container_client, blob_connection_string
from _config import CONTAINER_NAME


def list_json_blobs(prefix: Optional[str] = None) -> List[str]:
    """
    List all `.json` blob names in the configured container.

    Args:
            prefix: Optional blob name prefix to filter results.

    Returns:
            List of blob names ending with .json
    """
    print(f"Listing JSON blobs in container '{CONTAINER_NAME}'...")
    names: List[str] = []
    try:
        blob_iter = container_client.list_blobs(name_starts_with=prefix)
        for blob in blob_iter:
            if blob.name.lower().endswith(".json"):
                names.append(blob.name)
    except Exception as e:
        print(f"Error listing blobs: {e}")
        raise

    print(f"Found {len(names)} JSON blob(s).")
    return names


def download_json_blob(blob_name: str) -> Any:
    """
    Download a single JSON blob and return its parsed content.

    Returns Python object (dict/list) from the JSON.
    """
    try:
        blob_client = container_client.get_blob_client(blob_name)
        data = blob_client.download_blob().readall()
        return json.loads(data)
    except json.JSONDecodeError:
        print(f"Warning: Could not decode JSON from '{blob_name}'.")
        return None
    except Exception as e:
        print(f"Error downloading '{blob_name}': {e}")
        return None


def download_all_json(prefix: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Download and aggregate all JSON blobs into a flat list of documents.

    - If a blob contains a list, items are extended into the result.
    - If a blob contains a dict, it is appended.

    Args:
            prefix: Optional prefix to restrict which blobs are downloaded.

    Returns:
            List of document dicts aggregated from all JSON blobs.
    """
    docs: List[Dict[str, Any]] = []
    for name in list_json_blobs(prefix):
        print(f"Downloading '{name}'...")
        obj = download_json_blob(name)
        if obj is None:
            continue
        if isinstance(obj, list):
            docs.extend([x for x in obj if isinstance(x, dict)])
        elif isinstance(obj, dict):
            docs.append(obj)
        else:
            print(f"Warning: '{name}' does not contain a dict or list.")

    print(f"Aggregated {len(docs)} document(s) from JSON blobs.")
    return docs


def save_all_json(download_dir: str, prefix: Optional[str] = None) -> str:
    """
    Download all JSON blobs and save them to a local folder.

    Files are saved using their blob names relative to `download_dir`.

    Args:
            download_dir: Local directory to write files.
            prefix: Optional prefix to restrict which blobs are downloaded.

    Returns:
            The absolute path of the download directory.
    """
    os.makedirs(download_dir, exist_ok=True)
    blob_names = list_json_blobs(prefix)
    saved_count = 0
    for name in blob_names:
        print(f"Saving '{name}'...")
        local_path = os.path.join(download_dir, *name.split("/"))
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        # Skip if already saved locally
        if os.path.exists(local_path):
            print(f"Skipping '{name}' (already exists).")
            continue

        obj = download_json_blob(name)

        # Ensure nested folders are created to mirror blob paths
        local_path = os.path.join(download_dir, *name.split("/"))
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        if obj is not None:
            with open(local_path, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
            saved_count += 1
        else:
            # Fallback: write raw bytes to file if JSON parsing failed
            try:
                data = container_client.get_blob_client(name).download_blob().readall()
                with open(local_path, "wb") as f:
                    f.write(data)
                saved_count += 1
            except Exception as e:
                print(f"Failed to save raw content for '{name}': {e}")

    abs_dir = os.path.abspath(download_dir)
    print(f"Saved {saved_count} of {len(blob_names)} file(s) to '{abs_dir}'.")
    return abs_dir


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="List and download JSON blobs from Azure Storage"
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default=None,
        help="Optional prefix to filter blobs (e.g., 'folder/subfolder/')",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Only list JSON blobs and exit",
    )
    parser.add_argument(
        "--download",
        type=str,
        default=None,
        help="Download all JSON blobs to the given local directory",
    )
    parser.add_argument(
        "--aggregate",
        action="store_true",
        help="Aggregate JSON contents and print a summary count",
    )

    args = parser.parse_args()

    if args.list:
        names = list_json_blobs(args.prefix)
        for n in names:
            print(n)
        print(f"Total: {len(names)} JSON blob(s)")
    elif args.download:
        save_all_json(args.download, args.prefix)
    elif args.aggregate:
        docs = download_all_json(args.prefix)
        print(f"Aggregated documents: {len(docs)}")
    else:
        # Default behavior: list names then show quick aggregate count
        names = list_json_blobs(args.prefix)
        print(f"Total JSON blobs: {len(names)}")
        docs = download_all_json(args.prefix)
        print(f"Total aggregated documents: {len(docs)}")
