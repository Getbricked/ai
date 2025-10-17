import os
import json
import PyPDF2
from docx import Document
from ._utils import get_openai_embedding
from .credentials import container_client, endpoint, api_key
from _config import CONTAINER_NAME, EMBEDDING_DEPLOYMENT_NAME


def convert_to_json_and_upload(local_path):
    json_documents = []
    total_size = 0
    for filename in os.listdir(local_path):
        file_path = os.path.join(local_path, filename)
        doc_id = filename.replace(".", "_")  # Generate ID from filename
        content = ""
        category = "Unknown"
        source = "Local Storage"

        try:
            if filename.endswith(".txt"):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                category = "Article"  # Example categorization
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

                print(f"Checking if container '{CONTAINER_NAME}' exists...")
                if container_client.exists():
                    print(
                        f"✅ Container '{CONTAINER_NAME}' already exists. No action taken."
                    )
                else:
                    print(
                        f"Container '{CONTAINER_NAME}' does not exist. Creating it now..."
                    )
                    container_client.create_container()
                    print(f"✅ Successfully created container '{CONTAINER_NAME}'.")

                json_doc = {
                    "id": doc_id,
                    "content": content,
                    "category": category,
                    "source": source,
                    "contentVector": get_openai_embedding(
                        content, EMBEDDING_DEPLOYMENT_NAME, endpoint, api_key
                    ),  # Mock embedding
                }

                json_documents.append(json_doc)

                # Upload to Blob Storage
                blob_name = f"doc-{doc_id}.json"
                blob_client = container_client.get_blob_client(blob_name)
                blob_data = json.dumps(json_doc)
                blob_client.upload_blob(blob_data, overwrite=True)
                size = len(blob_data.encode("utf-8"))
                total_size += size
                print(
                    f"Converted and uploaded {blob_name} to Blob Storage ({size} bytes)."
                )
            else:
                print(f"No content extracted from {filename}")
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    print(f"Total uploaded: {total_size / 1024:.2f} KB")
    return json_documents
