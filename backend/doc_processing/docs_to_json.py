import os
import json
import logging
import PyPDF2
from docx import Document
import re
import time
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from _utils import get_openai_embeddings_batch
from _credentials import container_client, embed_endpoint, embed_api_key
from _config import CONTAINER_NAME, EMBEDDING_DEPLOYMENT_NAME

logger = logging.getLogger(__name__)


def convert_to_json_and_upload(local_path):
    start_time = time.perf_counter()
    json_documents = []
    total_size = 0

    logger.info("Checking if container '%s' exists...", CONTAINER_NAME)
    if container_client.exists():
        logger.info("Container '%s' already exists. No action taken.", CONTAINER_NAME)
    else:
        logger.info("Container '%s' does not exist. Creating it now...", CONTAINER_NAME)
        container_client.create_container()
        logger.info("Successfully created container '%s'.", CONTAINER_NAME)

    logger.info("Fetching existing documents from blob storage...")
    existing_blobs = set()
    try:
        blob_list = container_client.list_blobs()
        for blob in blob_list:
            existing_blobs.add(blob.name)
        logger.info("Found %d existing documents in storage.", len(existing_blobs))
    except Exception as e:
        logger.warning("Could not fetch existing blobs: %s", e)

    logger.info("Phase 1: Collecting paragraphs to process...")
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
                logger.info("Skipping unsupported file: %s", filename)
                continue

            if content:
                paragraphs = re.split(r"\n\n+", content)
                paragraphs = [p.strip() for p in paragraphs if p.strip()]

                logger.info("Found %d paragraphs in %s", len(paragraphs), filename)

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
                logger.info("No content extracted from %s", filename)
        except Exception as e:
            logger.error("Error processing %s: %s", filename, e)

    if not paragraphs_to_process:
        logger.info("No new paragraphs to process.")
        logger.info("Total time: %.2f seconds", time.perf_counter() - start_time)
        return json_documents

    logger.info("Collected %d paragraphs to process", len(paragraphs_to_process))

    logger.info("Phase 2: Generating embeddings in batches...")
    embed_start_time = time.perf_counter()
    texts = [p["content"] for p in paragraphs_to_process]
    embeddings = get_openai_embeddings_batch(
        texts,
        EMBEDDING_DEPLOYMENT_NAME,
        embed_endpoint,
        embed_api_key,
        max_batch_size=500,
    )
    embed_time = time.perf_counter() - embed_start_time
    logger.info("Generated %d embeddings", len(embeddings))

    logger.info("Phase 3: Uploading documents to blob storage (parallel)...")
    upload_phase_start_time = time.perf_counter()

    def _upload_blob(args):
        para_data, embedding = args
        try:
            json_doc = {
                "id": para_data["doc_id"],
                "content": para_data["content"],
                "category": para_data["category"],
                "source": para_data["source"],
                "contentVector": embedding,
            }
            blob_data = json.dumps(json_doc)
            blob_client = container_client.get_blob_client(para_data["blob_name"])
            t0 = time.perf_counter()
            blob_client.upload_blob(blob_data, overwrite=False)
            elapsed = time.perf_counter() - t0
            size = len(blob_data.encode("utf-8"))
            return (json_doc, size, elapsed, None)
        except Exception as e:
            return (None, 0, 0, f"Error uploading {para_data['blob_name']}: {e}")

    upload_items = [
        (para_data, embedding)
        for para_data, embedding in zip(paragraphs_to_process, embeddings)
        if embedding is not None
    ]

    json_documents = []
    total_size = 0
    upload_time = 0.0
    done = 0

    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(_upload_blob, item) for item in upload_items]
        for future in as_completed(futures):
            doc, size, elapsed, error = future.result()
            done += 1
            if error:
                logger.error(error)
            else:
                json_documents.append(doc)
                total_size += size
                upload_time += elapsed
            if done % 50 == 0 or done == len(upload_items):
                logger.info("Progress: %d/%d", done, len(upload_items))

    progress_time = time.perf_counter() - upload_phase_start_time - upload_time
    total_time = time.perf_counter() - start_time

    logger.info("Total uploaded: %.2f KB", total_size / 1024)
    logger.info("Successfully processed %d documents", len(json_documents))
    logger.info("Embed time: %.2f seconds", embed_time)
    logger.info("Upload time: %.2f seconds", upload_time)
    logger.info("Progress time: %.2f seconds", progress_time)
    logger.info("Total time: %.2f seconds", total_time)
    return json_documents


def upload_backup(local_path):
    start_time = time.perf_counter()
    total_size = 0

    logger.info("Checking if container '%s' exists...", CONTAINER_NAME)
    if not container_client.exists():
        logger.info("Container '%s' does not exist. Creating it now...", CONTAINER_NAME)
        container_client.create_container()
        logger.info("Successfully created container '%s'.", CONTAINER_NAME)
    else:
        logger.info("Container '%s' already exists. No action taken.", CONTAINER_NAME)

    existing_blobs = set()
    try:
        for blob in container_client.list_blobs():
            existing_blobs.add(blob.name)
        logger.info("Found %d existing documents in storage.", len(existing_blobs))
    except Exception as e:
        logger.warning("Could not fetch existing blobs: %s", e)

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
                logger.info("Skipping %s (already exists)", blob_name)
                continue

            blob_data = json.dumps(
                {
                    "id": doc_id,
                    "content": data.get("content", ""),
                    "contentVector": data.get("contentVector"),
                    "category": data.get("category", "Unknown"),
                    "source": data.get("source", "Local Storage"),
                }
            )

            blob_client = container_client.get_blob_client(blob_name)
            blob_client.upload_blob(blob_data, overwrite=False)
            size = len(blob_data.encode("utf-8"))
            total_size += size
            logger.info("Uploaded %s (%d bytes)", blob_name, size)

        except Exception as e:
            logger.error("Error processing %s: %s", filename, e)

    logger.info("Total uploaded: %.2f KB", total_size / 1024)
    logger.info("Upload time: %.2f seconds", time.perf_counter() - start_time)
    return total_size
