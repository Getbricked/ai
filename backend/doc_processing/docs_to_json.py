import os
import json
import PyPDF2
from docx import Document
import re
import time
from _utils import get_openai_embeddings_batch
from _credentials import container_client, embed_endpoint, embed_api_key
from _config import CONTAINER_NAME, EMBEDDING_DEPLOYMENT_NAME


def convert_to_json_and_upload(local_path):
    start_time = time.perf_counter()
    json_documents = []
    total_size = 0

    # Ensure container exists once
    print(f"Checking if container '{CONTAINER_NAME}' exists...")
    if container_client.exists():
        print(f"✅ Container '{CONTAINER_NAME}' already exists. No action taken.")
    else:
        print(f"Container '{CONTAINER_NAME}' does not exist. Creating it now...")
        container_client.create_container()
        print(f"✅ Successfully created container '{CONTAINER_NAME}'.")

    # Get list of existing blobs
    print("Fetching existing documents from blob storage...")
    existing_blobs = set()
    try:
        blob_list = container_client.list_blobs()
        for blob in blob_list:
            existing_blobs.add(blob.name)
        print(f"Found {len(existing_blobs)} existing documents in storage.")
    except Exception as e:
        print(f"Warning: Could not fetch existing blobs: {e}")

    # Phase 1: Collect all paragraphs that need processing
    print("\n📋 Phase 1: Collecting paragraphs to process...")
    paragraphs_to_process = []

    for filename in os.listdir(local_path):
        file_path = os.path.join(local_path, filename)
        base_id = filename.replace(".", "_")
        content = ""
        category = "Unknown"
        source = "Local Storage"

        try:
            if filename.endswith(".txt"):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                category = "Article"
            elif filename.endswith(".pdf"):
                with open(file_path, "rb") as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    content = " ".join(
                        page.extract_text()
                        for page in pdf_reader.pages
                        if page.extract_text()
                    ).strip()
                category = "PDF"
            elif filename.endswith(".json"):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    content = data.get("content", "")
                    category = data.get("category", "FAQ")
                    source = data.get("source", "Cybersecurity Forum")
            elif filename.endswith(".docx"):
                doc = Document(file_path)
                content = " ".join(
                    paragraph.text
                    for paragraph in doc.paragraphs
                    if paragraph.text.strip()
                ).strip()
                category = "Word"
            else:
                print(f"Skipping unsupported file: {filename}")
                continue

            if content:
                paragraphs = re.split(r"\n\n+", content)
                paragraphs = [p.strip() for p in paragraphs if p.strip()]

                print(f"Found {len(paragraphs)} paragraphs in {filename}")

                for idx, paragraph in enumerate(paragraphs, start=1):
                    doc_id = f"{base_id}_{idx}"
                    blob_name = f"doc-{doc_id}.json"

                    if blob_name in existing_blobs:
                        continue

                    paragraphs_to_process.append(
                        {
                            "doc_id": doc_id,
                            "blob_name": blob_name,
                            "content": paragraph,
                            "category": category,
                            "source": source,
                        }
                    )
            else:
                print(f"No content extracted from {filename}")
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    if not paragraphs_to_process:
        print("No new paragraphs to process.")
        print(f"✅ Total time: {time.perf_counter() - start_time:.2f} seconds")
        return json_documents

    print(f"✅ Collected {len(paragraphs_to_process)} paragraphs to process\n")

    # Phase 2: Generate embeddings in batches
    print(f"🔄 Phase 2: Generating embeddings in batches...")
    embed_start_time = time.perf_counter()
    texts = [p["content"] for p in paragraphs_to_process]
    embeddings = get_openai_embeddings_batch(
        texts,
        EMBEDDING_DEPLOYMENT_NAME,
        embed_endpoint,
        embed_api_key,
        max_batch_size=16,
    )
    embed_time = time.perf_counter() - embed_start_time
    print(f"✅ Generated {len(embeddings)} embeddings\n")

    # Phase 3: Upload documents in batches
    print(f"⬆️  Phase 3: Uploading documents to blob storage...")
    upload_phase_start_time = time.perf_counter()
    upload_time = 0.0
    upload_batch_size = 50

    for i in range(0, len(paragraphs_to_process), upload_batch_size):
        batch = paragraphs_to_process[i : i + upload_batch_size]
        batch_embeddings = embeddings[i : i + upload_batch_size]

        for para_data, embedding in zip(batch, batch_embeddings):
            if embedding is None:
                print(f"  ⚠️  Skipping {para_data['blob_name']} (embedding failed)")
                continue

            try:
                json_doc = {
                    "id": para_data["doc_id"],
                    "content": para_data["content"],
                    "category": para_data["category"],
                    "source": para_data["source"],
                    "contentVector": embedding,
                }

                json_documents.append(json_doc)

                blob_client = container_client.get_blob_client(para_data["blob_name"])
                blob_data = json.dumps(json_doc)
                upload_start_time = time.perf_counter()
                blob_client.upload_blob(blob_data, overwrite=False)
                upload_time += time.perf_counter() - upload_start_time
                size = len(blob_data.encode("utf-8"))
                total_size += size
                print(f"  ✓ Uploaded {para_data['blob_name']} ({size} bytes)")
            except Exception as e:
                print(f"  ✗ Error uploading {para_data['blob_name']}: {e}")

        # Print batch progress
        if (i + upload_batch_size) < len(paragraphs_to_process):
            print(
                f"  Progress: {min(i + upload_batch_size, len(paragraphs_to_process))}/{len(paragraphs_to_process)}"
            )

    progress_time = time.perf_counter() - upload_phase_start_time - upload_time
    total_time = time.perf_counter() - start_time

    print(f"\n✅ Total uploaded: {total_size / 1024:.2f} KB")
    print(f"✅ Successfully processed {len(json_documents)} documents")
    print(f"✅ Embed time: {embed_time:.2f} seconds")
    print(f"✅ Upload time: {upload_time:.2f} seconds")
    print(f"✅ Progress time: {progress_time:.2f} seconds")
    print(f"✅ Total time: {total_time:.2f} seconds")
    return json_documents


def upload_backup(local_path):
    start_time = time.perf_counter()
    total_size = 0

    print(f"Checking if container '{CONTAINER_NAME}' exists...")
    if not container_client.exists():
        print(f"Container '{CONTAINER_NAME}' does not exist. Creating it now...")
        container_client.create_container()
        print(f"✅ Successfully created container '{CONTAINER_NAME}'.")
    else:
        print(f"✅ Container '{CONTAINER_NAME}' already exists. No action taken.")

    existing_blobs = set()
    try:
        for blob in container_client.list_blobs():
            existing_blobs.add(blob.name)
        print(f"Found {len(existing_blobs)} existing documents in storage.")
    except Exception as e:
        print(f"Warning: Could not fetch existing blobs: {e}")

    for filename in os.listdir(local_path):
        if not filename.endswith(".json"):
            continue

        file_path = os.path.join(local_path, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            doc_id = data.get("id") or filename.replace(".", "_")
            blob_name = f"doc-{doc_id}.json"

            if blob_name in existing_blobs:
                print(f"Skipping {blob_name} (already exists)")
                continue

            blob_data = json.dumps(
                {
                    "id": doc_id,
                    "content": data.get("content", ""),
                    "category": data.get("category", "Unknown"),
                    "source": data.get("source", "Local Storage"),
                }
            )

            blob_client = container_client.get_blob_client(blob_name)
            blob_client.upload_blob(blob_data, overwrite=False)
            size = len(blob_data.encode("utf-8"))
            total_size += size
            print(f"Uploaded {blob_name} ({size} bytes)")

        except Exception as e:
            print(f"Error processing {filename}: {e}")

    print(f"Total uploaded: {total_size / 1024:.2f} KB")
    print(f"Upload time: {time.perf_counter() - start_time:.2f} seconds")
    return total_size
