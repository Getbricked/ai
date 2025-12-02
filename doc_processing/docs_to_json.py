import os
import json
import PyPDF2
from docx import Document
import re
from _utils import get_openai_embedding
from _credentials import container_client, embed_endpoint, embed_api_key
from _config import CONTAINER_NAME, EMBEDDING_DEPLOYMENT_NAME


def convert_to_json_and_upload(local_path):
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

    for filename in os.listdir(local_path):
        file_path = os.path.join(local_path, filename)
        base_id = filename.replace(".", "_")  # Generate base ID from filename
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
                # Split content into sentences
                sentences = re.split(r"(?<=[.!?])\s+", content)
                sentences = [s.strip() for s in sentences if s.strip()]

                print(f"Processing {filename}: {len(sentences)} sentences found")

                # Process each sentence
                for idx, sentence in enumerate(sentences, start=1):
                    doc_id = f"{base_id}_{idx}"

                    json_doc = {
                        "id": doc_id,
                        "content": sentence,
                        "category": category,
                        "source": source,
                        "contentVector": get_openai_embedding(
                            sentence,
                            EMBEDDING_DEPLOYMENT_NAME,
                            embed_endpoint,
                            embed_api_key,
                        ),
                    }

                    json_documents.append(json_doc)

                    # Upload to Blob Storage
                    blob_name = f"doc-{doc_id}.json"
                    blob_client = container_client.get_blob_client(blob_name)
                    blob_data = json.dumps(json_doc)
                    blob_client.upload_blob(blob_data, overwrite=True)
                    size = len(blob_data.encode("utf-8"))
                    total_size += size
                    print(f"  Uploaded {blob_name} ({size} bytes)")
            else:
                print(f"No content extracted from {filename}")
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    print(f"Total uploaded: {total_size / 1024:.2f} KB")
    return json_documents
