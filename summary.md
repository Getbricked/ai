## Chapter 3: System Analysis and Design

### 3.1 Introduction

This chapter presents the analysis and design of the cybersecurity question-answering system developed using Azure OpenAI and Azure AI Search. The system provides an intelligent assistant that answers user questions using organization-specific cybersecurity documents. It combines a React-based frontend with a FastAPI backend and several Azure cloud services (Azure OpenAI, Azure AI Search, and Azure Blob Storage). This chapter describes the overall architecture, functional and non-functional requirements, data and process flows, and the detailed design of the main components.

### 3.2 System Overview

The proposed system is a web-based question-answering platform specialized in cybersecurity. Users interact with the system through a browser-based chat interface. When a user submits a question, the frontend sends the request to a REST API exposed by the backend. The backend performs retrieval-augmented generation (RAG): it first retrieves relevant passages from a document index stored in Azure AI Search and then uses an Azure OpenAI large language model (LLM) to generate an answer grounded in those passages. The answer is returned to the frontend and rendered with support for Markdown and syntax highlighting.

The solution comprises the following main subsystems:

- Presentation layer: a Vite + React single-page application (SPA) located in the frontend folder (e.g., App.jsx and Chat.jsx).
- Application and integration layer: a FastAPI backend (server.py) implementing HTTP endpoints for chat, health checking, session management, and interaction with Azure services.
- Data and infrastructure layer: Azure resources defined in the configuration module (_config.py), including Azure OpenAI, Azure AI Search, Azure Storage accounts, and resource groups, as well as local utilities for deployment and document ingestion (deploy.py, upload_doc.py, and modules under azure_setup and doc_processing).

### 3.3 Requirements Analysis

#### 3.3.1 User Stories

The following user stories summarize the main goals from the perspective of different stakeholders:

- US1 - As a cybersecurity analyst, I want to ask about a specific CVE (e.g., "CVE-2021-44228") so that I can quickly understand its impact and recommended mitigations without manually browsing lengthy vulnerability reports.
- US2 - As a security engineer, I want to query "How do I mitigate the Log4j vulnerability?" so that I receive consolidated, context-aware guidance grounded in our documentation and trusted cybersecurity sources.
- US3 - As an IT administrator, I want to ask general questions such as "How can I secure a home network?" and "How do I reduce the risk of ransomware?" so that I can obtain practical best-practice recommendations in natural language.
- US4 - As a researcher, I want to explore information on adversary groups and attack techniques (e.g., MITRE ATT&CK groups) so that I can study trends and relationships through a conversational interface.
- US5 - As a user, I want my conversation history to be preserved across questions so that I can refine my queries iteratively without repeating context.
- US6 - As a maintainer, I want to add new cybersecurity documents and have them automatically indexed so that the assistant can use the latest information without code changes.

#### 3.3.2 Functional Requirements

Based on these user stories and the implemented code, the core functional requirements are as follows:

- FR1 - User query submission: The system shall allow users to submit free-text cybersecurity questions through a chat-like web interface.
- FR2 - Session management: The system shall create new chat sessions and associate messages with a session identifier, enabling multi-turn conversations (server endpoints /api/new-session and /api/chat, and client-side session state in Chat.jsx).
- FR3 - Retrieval of relevant documents: The system shall retrieve relevant document fragments from an Azure AI Search index based on the user question. This is implemented using the SearchClient and search_index function, which perform vector and keyword search over an index defined by INDEX_NAME and SEARCH_NAME in _config.py.
- FR4 - Answer generation using Azure OpenAI: The system shall generate an answer by calling an Azure OpenAI chat completion model (GPT_DEPLOYMENT_NAME) using the retrieved context as input (get_openai_completion in _utils.py).
- FR5 - Cybersecurity-focused behavior: The assistant shall behave as a cybersecurity specialist and restrict answers to the provided context. This behavior is enforced through a system prompt constructed in server.py.
- FR6 - Response delivery: The system shall return the generated answer to the frontend through a JSON API (/api/chat) and display it to the user in the chat interface (sendMessage in client.js and Message.jsx).
- FR7 - Session persistence: The system shall allow saving sessions locally in the browser and, on demand, persist them to disk on the server side (frontend sessions.js utilities and /api/save-session endpoint using save_session_to_file in server.py).
- FR8 - Health monitoring: The system shall expose a simple health-check endpoint (/health) to verify that the backend is running.

#### 3.3.3 Non-Functional Requirements

From the design and technology stack, the following non-functional requirements are derived:

- NFR1 - Security: The system shall authenticate to Azure resources using managed identities or service principals via DefaultAzureCredential. Access to Azure OpenAI, Search, and Storage is performed using strongly scoped keys and credentials obtained at runtime (_credentials.py and _utils.py).
- NFR2 - Performance: The system shall retrieve relevant documents and generate answers with acceptable latency for interactive use. Vector search (using OpenAI embeddings) and batched embedding utilities (get_openai_embeddings_batch) are used to minimize the number of API calls.
- NFR3 - Scalability: The architecture shall support horizontal scaling of the backend and Azure services. FastAPI is stateless with respect to long-term data, and stateful elements (embeddings index, document storage, and OpenAI models) reside in managed Azure services.
- NFR4 - Availability and reliability: Azure managed services (Search, Storage, and OpenAI) provide redundancy and SLA-backed availability. The health endpoint supports monitoring.
- NFR5 - Usability: The frontend shall offer an intuitive chat interface, including message history, suggestion chips for common cybersecurity questions, and Markdown rendering for rich responses.
- NFR6 - Maintainability: Configuration values (e.g., resource names, model deployments, and locations) are centralized in _config.py, and reusable utilities for Azure interactions are located in _utils.py and azure_setup modules, thereby supporting easier maintenance and extension.

### 3.4 System Architecture

#### 3.4.1 High-Level Architecture and Diagram

The system follows a three-tier web architecture that can be summarized conceptually as:

**User -> Frontend (React SPA) -> Python Backend (FastAPI) -> Azure OpenAI / Azure AI Search / Azure Storage**.

In the thesis document, this is represented as a block diagram with the following elements:

- A "User" node representing the analyst or administrator interacting via a web browser.
- A "Frontend" node (Vite + React) that handles the chat user interface and issues HTTP requests to the backend.
- A "Python Backend" node (FastAPI) which exposes REST endpoints, performs validation, orchestrates retrieval-augmented generation, and manages sessions.
- A "Vector Search / Indexing" node representing Azure AI Search (vector index over cybersecurity documents stored in Azure Storage).
- An "LLM Service" node representing Azure OpenAI embeddings and chat completion deployments.

Arrows in the diagram indicate the direction of requests and responses: user messages flow from the browser to the frontend, to the backend, then to Azure Search and Azure OpenAI, and finally back to the user as an answer.

#### 3.4.2 Data Flow

The data flow from raw cybersecurity documents to user answers comprises two main phases: offline ingestion and online querying.

1. **Offline ingestion phase**
   - Raw documents (e.g., cybersecurity guidelines, CVE descriptions, MITRE group information, and scraped forum content) are stored under backend/docs.
   - The ingestion script upload_doc.py loads these documents, cleans and converts them into structured JSON records.
   - The script uploads the processed documents to an Azure Blob Storage container (CONTAINER_NAME) within the configured storage account (STORAGE_NAME).
   - Azure AI Search indexes the uploaded documents, storing content, metadata (e.g., source, type), and vector embeddings where applicable.

2. **Online query phase**
   - The user submits a question through the React chat interface.
   - The frontend calls the /api/chat endpoint of the FastAPI backend with the question and session identifier.
   - The backend embeds the question using Azure OpenAI (get_openai_embedding) and queries the Azure AI Search index (search_index) to retrieve the most relevant chunks.
   - Retrieved content is concatenated into a context string, which is combined with the current conversation history to form the prompt for Azure OpenAI's chat completion endpoint (get_openai_completion).
   - Azure OpenAI returns an answer grounded in the retrieved context, which the backend sends back as JSON to the frontend, where it is rendered and displayed to the user.

#### 3.4.3 Backend Architecture

The backend is implemented using FastAPI in server.py. Its key architectural elements include:

- API models: Pydantic models (QueryRequest, NewSessionResponse, SaveSessionRequest) define the structure of incoming and outgoing payloads. This enforces input validation and clear contracts for the API.
- Session store: An in-memory Python dictionary (sessions = {}) holds conversation histories keyed by session_id. For each session, the backend appends user and assistant messages after a successful call to Azure OpenAI. The implementation notes that a production deployment would use a persistent store such as Redis or a database.
- CORS configuration: The application configures CORSMiddleware to allow requests from the local Vite development server and Azure development tunnels, enabling safe cross-origin interaction during development.
- Azure Search integration: The function get_search_client uses get_search_admin_key from _utils.py to obtain the Search admin key and constructs a SearchClient bound to the configured index. The search_index helper (in backend/search_query/search_query.py) is then used to perform vector and keyword search.
- Azure OpenAI integration: Utility functions get_openai_embedding and get_openai_completion in _utils.py wrap the AzureOpenAI client. The backend uses these to embed user questions and generate chat completions based on context.
- Session persistence to disk: save_session_to_file writes session data as JSON files into the frontend/sessions folder, creating it if necessary. This design choice simplifies subsequent loading and analysis of historical chats.

#### 3.4.4 Frontend Architecture

The frontend is built with React and Vite and organized around a main chat component:

- Root composition: main.jsx creates the React root and renders App.jsx. App.jsx wraps the Chat component as the main content of the single-page application.
- Chat controller: Chat.jsx maintains local state for messages, input text, loading and error indicators, the current session identifier, saved session metadata, and UI state (e.g., sidebar collapse). It orchestrates calls to the backend via client.js and to local storage via sessions.js.
- API client: client.js defines functions createNewSession and sendMessage that perform HTTP POST requests to /api/new-session and /api/chat, respectively. These functions encapsulate error handling and payload transformation for the React components.
- Message rendering: Message.jsx receives role and content props and renders them using ReactMarkdown with remark-gfm and rehype-highlight. This allows the assistant to return rich text with lists, tables, code snippets, and links.
- Session sidebar: SessionSidebar.jsx displays a list of locally stored sessions, enables loading a previous conversation, and supports session deletion. The Chat component connects these actions to the underlying session utilities and backend persistence.

### 3.5 Detailed Design

#### 3.5.1 Chat Workflow

The end-to-end chat workflow consists of the following steps:

1. Session initialization: On component mount, Chat.jsx calls initializeSession, which invokes createNewSession in client.js. The backend endpoint /api/new-session generates a UUID session_id, stores an empty message list in the sessions dictionary, and returns the identifier to the client.
2. Message composition: The user enters a question in the prompt bar or selects one of the predefined suggestion chips. Chat.jsx appends the question as a user-role message to the local messages array.
3. API request: Chat.jsx calls sendMessage(question, sessionId), which issues a POST request with a JSON body containing the question text and the current session_id.
4. Input validation: The backend's chat function (server.py) trims the question string and rejects empty inputs with an HTTP 400 error.
5. Vector embedding: The backend calls get_openai_embedding, passing EMBEDDING_DEPLOYMENT_NAME, embed_endpoint, and embed_api_key. Azure OpenAI returns a dense vector representation of the user question.
6. Document retrieval: The search_index helper executes a vector search in Azure AI Search using the question embedding. Top-k results are retrieved. Each hit includes a score and a document payload containing content and source fields. Results with scores above a threshold (e.g., 0.55) are appended to the context_parts list. If no high-scoring results are identified, the system falls back to keyword search using query_text.
7. Prompt construction: The backend constructs a messages list for the chat completion call. It starts with a system message that constrains the assistant to act as a cybersecurity specialist and to rely only on the provided context. It then appends the historical messages for the current session from the sessions dictionary, followed by the new user message containing both the context and the current question.
8. Answer generation: The backend calls get_openai_completion, which uses AzureOpenAI to invoke the configured GPT model deployment. The resulting answer string is extracted from the first completion choice.
9. Session update: The backend appends the raw question and generated answer to the sessions dictionary for the given session_id, preserving the conversation history for subsequent turns.
10. Response delivery: The backend returns a JSON object containing answer and session_id. The frontend updates its messages state with a new assistant-role message and re-renders the UI. Message.jsx renders the answer with Markdown support and opens external links in a new browser tab.

#### 3.5.2 Session Management and Persistence

Session management is split between client and server:

- In-memory session store: The backend keeps an in-memory dictionary mapping session identifiers to lists of message objects. This supports multi-turn context for the RAG prompt, but is ephemeral across server restarts.
- Browser-side persistence: The frontend uses helper functions (loadAllSessions, saveSession, createSessionObject, getSessionById, deleteSession) to store and retrieve session objects from local storage. Chat.jsx calls these utilities on page load and when the user starts a new chat or switches sessions.
- Disk persistence: The /api/save-session endpoint accepts a SaveSessionRequest containing session_id, user_id, and messages. It uses save_session_to_file to serialize the session to JSON and writes it into the frontend/sessions directory, enabling later offline analysis or backup of chat histories.
- Lifecycle hooks: A beforeunload event handler in Chat.jsx ensures that, immediately before the page is closed or refreshed, any non-empty current session is saved locally. This design reduces the risk of losing conversation history due to accidental page closure.

#### 3.5.3 Document Ingestion and Indexing

The backend provides a separate ingestion pipeline for cybersecurity documents:

- Configuration: The target resource group, storage account, container, search service, and index name are defined in _config.py (e.g., RG_NAME, STORAGE_NAME, CONTAINER_NAME, SEARCH_NAME, INDEX_NAME).
- Deployment: The deploy.py script creates or configures the necessary Azure resources, including Azure OpenAI deployments for embeddings and chat models, Azure Blob Storage, and the Azure AI Search index. It uses the management clients exposed in _utils.py and azure_setup modules.
- Upload and indexing: The upload_doc.py script scans backend/docs, converts supported document formats (e.g., .txt, .pdf, .docx) into a JSON representation, uploads them to the configured blob container, and populates the Azure AI Search index with document chunks and associated metadata.

This separation between online query handling and offline ingestion allows the system to be updated with new cybersecurity documents without impacting the availability of the chat service.

### 3.6 Design Considerations and Rationale

Several design decisions emerge from the implementation:

- Use of Retrieval-Augmented Generation: Rather than allowing the LLM to answer from general knowledge, the system constrains the model with retrieved context from organization-specific documents. This improves factual accuracy and ensures that answers are grounded in the cybersecurity materials provided.
- Azure-native integration: The use of Azure OpenAI, Azure AI Search, and Azure Storage leverages managed services for scalability, security, and operational convenience. Credential management via DefaultAzureCredential aligns with best practices for cloud authentication.
- Thin backend, rich frontend: Most interaction logic (session switching, chip suggestions, auto-scrolling, and text area resizing) is implemented in the React frontend, while the backend is focused on stateless orchestration of AI and search services.
- Modular utilities: Functions for obtaining subscription IDs, search keys, blob connection strings, and OpenAI credentials are encapsulated in _utils.py. This reduces duplication and centralizes Azure-specific logic.
- Development vs. production: The code comments explicitly note that sessions are stored in memory only for development purposes and suggest replacing this with Redis or a database in a production deployment. Similarly, CORS and origin settings are configured for local development and development tunnels.

### 3.7 Summary

This chapter has described the system analysis and design of the Azure-based cybersecurity question-answering platform. The system combines a React frontend, a FastAPI backend, and Azure cloud services to provide retrieval-augmented responses grounded in organization-specific documents. Functional requirements such as query handling, document retrieval, answer generation, and session management are supported by a layered architecture that separates presentation, application logic, and data services. Non-functional requirements around security, performance, scalability, and usability are addressed through the choice of technologies and design patterns. The next chapter focuses on the implementation details and experimental evaluation of the system.

### 3.8 Code Snippets

The following excerpts illustrate the core request flow and API contract described in this chapter.

```python
@app.post("/api/chat")
def chat(req: QueryRequest):
      question = (req.question or "").strip()
      if not question:
            raise HTTPException(status_code=400, detail="Missing 'question'")

      query_vector = get_openai_embedding(
            question,
            EMBEDDING_DEPLOYMENT_NAME,
            embed_endpoint,
            embed_api_key,
      )
      results = search_index(search_client, vector=query_vector, top_k=25)
```

```javascript
export async function sendMessage(question, sessionId = null) {
   const res = await fetch(`${baseURL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, session_id: sessionId })
   })
   const data = await res.json()
   return { answer: data?.answer, session_id: data?.session_id }
}
```

## Chapter 4: Infrastructure Automation

### 4.1 Introduction

This chapter describes the automation of the Azure infrastructure that underpins the cybersecurity question-answering system. Instead of creating resources manually through the Azure Portal, Python scripts and Azure SDK libraries are used to provision and configure the required services programmatically. This approach aligns with modern DevOps practices and supports reproducible, version-controlled deployments.

### 4.2 Azure SDK for Python

The system uses several Azure SDK for Python libraries to manage resources and authenticate securely:

- **azure-identity**: Provides DefaultAzureCredential, which automatically discovers credentials from the environment (e.g., Azure CLI login, managed identity, or service principal). This is used in _utils.py to authenticate management clients and retrieve OpenAI endpoints and keys.
- **azure-mgmt-cognitiveservices**: Used in _utils.py to access CognitiveServicesManagementClient and programmatically obtain the endpoint and keys of the Azure OpenAI resource.
- **azure-mgmt-search**: Provides SearchManagementClient, which is used in _utils.py and deploy.py to manage Azure AI Search services and retrieve admin keys.
- **azure-mgmt-storage**: Provides StorageManagementClient, which is used to retrieve storage account keys and build a connection string for Azure Blob Storage.
- **azure-search-documents**: Used at runtime in server.py to create a SearchClient that queries the cybersecurity document index.

These libraries enable the Python code to perform end-to-end automation: creating resources, retrieving credentials, and integrating backend dependencies at deployment time.

### 4.3 Automation Scripts

The main automation logic is encapsulated in backend/deploy.py and the helper functions defined in _utils.py and azure_setup modules. The deployment process typically performs the following steps:

1. Authenticate using DefaultAzureCredential.
2. Discover the active subscription ID (get_subscription_id in _utils.py).
3. Create or reuse resource groups for compute, search, and storage (RG_NAME and STORAGE_RG_NAME in _config.py).
4. Create or configure an Azure OpenAI resource and deploy the embedding and chat models (EMBEDDING_MODEL_NAME / EMBEDDING_DEPLOYMENT_NAME and GPT_MODEL_NAME / GPT_DEPLOYMENT_NAME).
5. Create a storage account (STORAGE_NAME) and a documents container (CONTAINER_NAME).
6. Create an Azure AI Search service (SEARCH_NAME) and a search index (INDEX_NAME) with appropriate fields for content, metadata, and vector fields.

Once deploy.py has run successfully, the environment is ready for document ingestion and for serving online queries.

### 4.4 Automated Teardown (Delete All Deployment Resources)

Infrastructure automation in this project also includes an automated teardown path to delete all deployed resources when resetting environments, cleaning up test deployments, or controlling cloud costs.

The main cleanup workflow is implemented in backend/delete.py and performs these steps:

1. Authenticate using DefaultAzureCredential and discover the active subscription.
2. Delete Azure OpenAI deployments (EMBEDDING_DEPLOYMENT_NAME and GPT_DEPLOYMENT_NAME).
3. Delete and purge the Azure OpenAI account (OPENAI_NAME) to fully remove soft-deleted artifacts.
4. Delete the Azure AI Search service (SEARCH_NAME).
5. Delete the primary resource group (RG_NAME), removing all remaining resources under it.

For storage teardown, backend/storage_reset.py provides a dedicated reset routine that deletes the storage account (STORAGE_NAME) and then deletes the storage resource group (STORAGE_RG_NAME).

Together, these scripts provide full lifecycle automation: create with deploy.py and remove with delete.py/storage_reset.py.

```python
def delete():
   credential = DefaultAzureCredential()
   subscription_id = get_subscription_id(credential)

   delete_deployment(cognitive_client, RG_NAME, OPENAI_NAME, EMBEDDING_DEPLOYMENT_NAME)
   delete_deployment(cognitive_client, RG_NAME, OPENAI_NAME, GPT_DEPLOYMENT_NAME)
   delete_openai_resource(cognitive_client, RG_NAME, OPENAI_NAME)
   purge_openai_resource(cognitive_client, RG_NAME, OPENAI_NAME, LOCATION)
   delete_search_service(search_client, RG_NAME, SEARCH_NAME)
   delete_resource_group(resource_client, RG_NAME)
```

### 4.5 Configuration Management and Secrets Handling

Configuration for the automated infrastructure is centralized in backend/_config.py, which contains logical names for resource groups, services, model deployments, and storage accounts. Sensitive information (such as service principal secrets or keys) is not hard-coded in the repository. Instead:

- Authentication to Azure uses DefaultAzureCredential, which reads credentials from the environment or managed identity.
- API keys for Azure OpenAI and Azure AI Search are retrieved at runtime through management APIs (get_azure_openai_credentials and get_search_admin_key in _utils.py) instead of being stored in plain text.
- On the frontend side, the base URL of the backend API is stored in an environment file (.env) via the VITE_API_BASE_URL variable, keeping deployment-specific configuration separate from the code.

This design reduces the risk of accidental key exposure and supports deployment across multiple environments (development, staging, production) with different configuration values.

### 4.6 Batch Operation in the Ingestion Pipeline

Before summarizing this chapter, it is important to explain the batch operation pattern used in the data ingestion flow.

In this project, batch operation means grouping many items into one API call or one processing cycle instead of sending one request per item. The implementation appears in two key places:

- **Batch embedding generation**: `get_openai_embeddings_batch` in `backend/_utils.py` sends a list of texts per request (`input=chunk`) and loops with a configurable `max_batch_size`.
- **Batch upload loop**: `backend/doc_processing/docs_to_json.py` processes paragraphs in groups (`upload_batch_size = 50`) and uploads them in a batched loop with progress reporting.

Why we use batch operation:

- Reduce network round-trips and per-request overhead.
- Improve throughput when processing many document chunks.
- Better align with API quota/rate-limit behavior by controlling request volume.
- Keep output order stable by sorting embedding response items by index, which helps maintain chunk-to-embedding alignment.
- Improve failure handling by isolating failures per chunk and continuing the overall pipeline.

Comparison of results with and without batch operation:

| Aspect | With batch operation | Without batch operation |
|---|---|---|
| API calls for embeddings | About `ceil(N / B)` calls for `N` texts and batch size `B` | `N` calls (one call per text) |
| End-to-end ingestion time | Typically lower for large datasets due to fewer round-trips | Typically higher because call overhead repeats for every item |
| Throughput | Higher and more stable for bulk ingestion | Lower, especially as dataset size grows |
| Rate-limit pressure pattern | Fewer, larger calls; easier to tune with `max_batch_size` | Many small calls; can trigger frequent throttling overhead |
| Error impact | A failed batch affects only that chunk; pipeline continues with placeholders (`None`) | A failed single call affects one item, but frequent retries can increase total runtime |
| Implementation complexity | Slightly higher (chunking, alignment, progress tracking) | Simpler logic but weaker scalability |

In this codebase specifically, batching is most beneficial during offline document preparation and indexing, where the same workflow must handle many paragraphs/documents in sequence.

Sources used for this section:

1. Project code:
    - `backend/_utils.py` (`get_openai_embeddings_batch`, batch loop and response ordering).
    - `backend/doc_processing/docs_to_json.py` ("Phase 2: Generating embeddings in batches", `max_batch_size=16`, and upload loop with `upload_batch_size=50`).
    - `backend/search_query/search_query.py` (`upload_documents_to_search`, list upload pattern to Azure AI Search).
2. Microsoft documentation:
    - Azure OpenAI embeddings guidance: supports array inputs in one request and states array-size/token constraints.
    - Azure AI Search Python `SearchClient` documentation: `upload_documents(documents: List[Dict])` and `index_documents(batch: IndexDocumentsBatch)` define list/batch document operations.
3. OpenAI developer documentation:
    - Embeddings guide describing embedding vectors, token-based usage, and examples using list-style `input`.

Batch operation code snippet:

```python
# 1) Batch embedding generation
def get_openai_embeddings_batch(
    texts, embedding_name, endpoint, api_key, max_batch_size=50
):
    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version="2023-05-15",
    )

    embeddings = []
    for i in range(0, len(texts), max_batch_size):
        chunk = texts[i : i + max_batch_size]
        response = client.embeddings.create(model=embedding_name, input=chunk)
        ordered = sorted(response.data, key=lambda x: x.index)
        embeddings.extend([item.embedding for item in ordered])

    return embeddings


# 2) Batched upload loop
upload_batch_size = 50
for i in range(0, len(paragraphs_to_process), upload_batch_size):
    batch = paragraphs_to_process[i : i + upload_batch_size]
    batch_embeddings = embeddings[i : i + upload_batch_size]

    for para_data, embedding in zip(batch, batch_embeddings):
        if embedding is None:
            continue

        json_doc = {
            "id": para_data["doc_id"],
            "content": para_data["content"],
            "category": para_data["category"],
            "source": para_data["source"],
            "contentVector": embedding,
        }

        blob_client = container_client.get_blob_client(para_data["blob_name"])
        blob_client.upload_blob(json.dumps(json_doc), overwrite=False)
```

### 4.7 Summary

Infrastructure automation is achieved using Azure's Python SDKs and a set of deployment and teardown scripts that provision OpenAI, Search, and Storage resources from code and can automatically delete them when needed. Centralized configuration and secure credential handling contribute to a reproducible and secure DevOps pipeline for the system.

### 4.8 Code Snippets

The deployment and credential-management logic is implemented as follows.

```python
def deploy():
   credential = DefaultAzureCredential()
   subscription_id = get_subscription_id(credential)

   create_resource_group(resource_client, RG_NAME, LOCATION)
   create_resource_group(resource_client, STORAGE_RG_NAME, LOCATION)
   create_storage_account(storage_client, STORAGE_RG_NAME, STORAGE_NAME, LOCATION)

   create_openai_resource(cognitive_client, RG_NAME, OPENAI_NAME, LOCATION)
   deploy_model(cognitive_client, RG_NAME, OPENAI_NAME, EMBEDDING_MODEL_NAME, EMBEDDING_DEPLOYMENT_NAME, version="1", capacity=350)
   deploy_model(cognitive_client, RG_NAME, OPENAI_NAME, GPT_MODEL_NAME, GPT_DEPLOYMENT_NAME, version="2024-07-18", capacity=200)
```

```python
def get_search_admin_key(credential, subscription_id, rg_name, search_name):
   search_client = SearchManagementClient(credential, subscription_id)
   keys = search_client.admin_keys.get(rg_name, search_name)
   return keys.primary_key


def get_blob_service_connection_string(credential, subscription_id, rg_name, storage_account_name):
   storage_client = StorageManagementClient(credential, subscription_id)
   keys = storage_client.storage_accounts.list_keys(rg_name, storage_account_name)
   account_key = keys.keys[0].value
   return (
      f"DefaultEndpointsProtocol=https;"
      f"AccountName={storage_account_name};"
      f"AccountKey={account_key};"
      f"EndpointSuffix=core.windows.net"
   )
```

```python
def delete():
   credential = DefaultAzureCredential()
   subscription_id = get_subscription_id(credential)

   delete_deployment(cognitive_client, RG_NAME, OPENAI_NAME, EMBEDDING_DEPLOYMENT_NAME)
   delete_deployment(cognitive_client, RG_NAME, OPENAI_NAME, GPT_DEPLOYMENT_NAME)
   delete_openai_resource(cognitive_client, RG_NAME, OPENAI_NAME)
   purge_openai_resource(cognitive_client, RG_NAME, OPENAI_NAME, LOCATION)
   delete_search_service(search_client, RG_NAME, SEARCH_NAME)
   delete_resource_group(resource_client, RG_NAME)
```

### 4.9 Source Citations for Section 4.6

The following sources were used to write Section 4.6 (Batch Operation in the Ingestion Pipeline):

1. Local project code (primary evidence)
    - backend/_utils.py, line 135: get_openai_embeddings_batch definition.
    - backend/_utils.py, line 154: embeddings call with list input (`input=chunk`).
    - backend/doc_processing/docs_to_json.py, line 119: embedding batch size (`max_batch_size=16`).
    - backend/doc_processing/docs_to_json.py, line 125: upload batch size (`upload_batch_size = 50`).
    - backend/search_query/search_query.py, line 137: Azure Search list upload (`upload_documents(documents=documents)`).

2. Microsoft documentation
    - Azure OpenAI embeddings guide (array-input limits and token constraints):
      https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/embeddings
    - Azure AI Search Python SearchClient API (batch/list document operations):
      https://learn.microsoft.com/en-us/python/api/azure-search-documents/azure.search.documents.searchclient

3. OpenAI documentation
    - OpenAI embeddings guide (embedding usage and list-style input examples):
      https://developers.openai.com/api/docs/guides/embeddings

Access date for online sources: March 25, 2026.

## Chapter 5: Data Preparation for the Cybersecurity Domain

### 5.1 Introduction

The effectiveness of a retrieval-augmented question-answering system critically depends on the quality and structure of its underlying documents. This chapter explains how cybersecurity-specific data is prepared—from sourcing to preprocessing, chunking, and embedding—before being indexed in Azure AI Search.

### 5.2 Data Sourcing

The system is designed to ingest cybersecurity materials from multiple types of sources, including but not limited to:

- Official vulnerability databases and advisories (e.g., CVE descriptions, vendor bulletins).
- Structured knowledge bases such as MITRE ATT&CK group and technique descriptions.
- Cybersecurity best-practice documents, guidelines, and incident response playbooks.
- Content scraped or downloaded from specialized forums and Q&A platforms relevant to cybersecurity (e.g., professional discussion boards or curated security communities).

In the implementation, raw text files and processed JSON documents are placed under backend/docs and backup/doc_*.json. These files represent the cybersecurity corpus that the system later uses to answer questions.

The primary automated data collection workflow targets the MITRE ATT&CK knowledge base and is implemented across two Python scripts: `mitre_list_scrape.py` and `link_scrape.py`. The pipeline operates in two distinct phases: first collecting a catalogue of URLs from MITRE listing pages, and then visiting each of those URLs to extract the actual content.

#### 5.2.1 Phase 1 — Collecting the Link Catalogue

The first script, `mitre_list_scrape.py`, is responsible for discovering all the individual resource URLs from MITRE ATT&CK's high-level listing pages. Rather than hard-coding URLs, the script dynamically scrapes MITRE's own table-based index pages for each data category.

The script defines the root listing URLs as constants:

```python
MITRE_ENTERPRISE_URL = "https://attack.mitre.org/techniques/enterprise/"
MITRE_GROUPS_URL     = "https://attack.mitre.org/groups/"
MITRE_ICS_TACTICS_URL    = "https://attack.mitre.org/tactics/ics/"
MITRE_MOBILE_TACTICS_URL = "https://attack.mitre.org/tactics/mobile/"
MITRE_MITIGATIONS_ENTERPRISE_URL = "https://attack.mitre.org/mitigations/enterprise/"
MITRE_MITIGATIONS_MOBILE_URL     = "https://attack.mitre.org/mitigations/mobile/"
MITRE_MITIGATIONS_ICS_URL        = "https://attack.mitre.org/mitigations/ics/"
```

A generic helper function `_scrape_listing_table` handles the table-parsing logic shared across all categories. It fetches the listing page, parses the HTML with BeautifulSoup, and iterates over every table row. For each row it first tries to match the ID pattern (e.g., `G\d{4}` for groups) in the first cell; if that fails it searches for any anchor whose `href` matches the expected path prefix. The dual approach makes the scraper resilient to minor layout changes.

```python
def _scrape_listing_table(url, id_regex, href_prefix, href_extract_regex, limit=None):
    soup = BeautifulSoup(requests.get(url, timeout=30).text, "html.parser")
    results = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        first = tds[0].get_text(strip=True)
        if re.match(id_regex, first):                          # primary: ID in first cell
            item_id  = first
            name     = tds[1].get_text(strip=True)
            item_url = f"https://attack.mitre.org{tds[1].find('a')['href']}"
            desc     = max([td.get_text(" ", strip=True) for td in tds[2:]], key=len, default="")
        else:                                                  # fallback: match any link
            a = tr.find("a", href=True)
            if not (a and href_prefix in a["href"]):
                continue
            m = re.search(href_extract_regex, a["href"])
            item_id, item_url = (m.group(1) if m else None), f"https://attack.mitre.org{a['href']}"
            name = tds[1].get_text(" ", strip=True) if len(tds) > 1 else ""
            desc = ""
        if item_id and name and item_url:
            results.append((item_id, name, item_url, desc))
    return results
```

For enterprise techniques, a dedicated function `collect_mitre_enterprise_techniques` handles the additional complexity of sub-techniques. MITRE's techniques table uses a two-row pattern: a parent technique row (e.g., `T1548`) followed by sub-technique rows whose second cell contains a dot-prefixed sub-code (e.g., `.001`). The scraper tracks the most recently seen parent ID and concatenates it with the sub-code to produce composite identifiers such as `T1548.001`.

```python
def collect_mitre_enterprise_techniques(limit=None):
    resp = requests.get(MITRE_ENTERPRISE_URL, timeout=30)
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    current_tech_id = None

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue
            id_text = tds[0].get_text(strip=True)

            if re.match(r"^T\d+$", id_text):           # parent technique
                name = tds[1].get_text(strip=True)
                url  = f"https://attack.mitre.org/techniques/{id_text}/"
                results.append((id_text, name, url))
                current_tech_id = id_text

            elif len(tds) >= 3 and re.match(r"^\.\d{3}$", tds[1].get_text(strip=True)):
                sub_id   = f"{current_tech_id}{tds[1].get_text(strip=True)}"
                sub_name = tds[2].get_text(strip=True)
                sub_url  = f"https://attack.mitre.org/techniques/{current_tech_id}/{tds[1].get_text(strip=True)[1:]}/"
                results.append((sub_id, sub_name, sub_url))
    return results
```

Once all entries are collected, the `main` function writes each category to a plain-text file under `backend/scraping/list/`. Each line in these files follows the format `ID - Name - URL` (with an optional description field for listing categories):

```
G0018 - admin@338 - https://attack.mitre.org/groups/G0018 - admin@338 is a China-based cyber threat group...
G1030 - Agrius    - https://attack.mitre.org/groups/G1030 - Agrius is an Iranian threat actor active since 2020...
```

```python
def write_mitre_output(entries, output_path):
    lines = [f"{tid} - {name} - {url}" for tid, name, url in entries]
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
```

The `main` function executes all collection jobs and writes the following output files:

```python
entries = collect_mitre_enterprise_techniques()
write_mitre_output(entries, "list/mitre_enterprise_techniques.txt")

for category, out_path in [
    ("groups",                   "list/mitre_groups.txt"),
    ("mobile_tactics",           "list/mitre_mobile_tactics.txt"),
    ("ics_tactics",              "list/mitre_ics_tactics.txt"),
    ("mitigations_enterprise",   "list/mitre_mitigations_enterprise.txt"),
    ("mitigations_mobile",       "list/mitre_mitigations_mobile.txt"),
    ("mitigations_ics",          "list/mitre_mitigations_ics.txt"),
]:
    items = collect_mitre(category)
    with open(out_path, "w", encoding="utf-8") as fh:
        for item_id, name, url, desc in items:
            fh.write(f"{item_id} - {name} - {url} - {desc}\n\n")
```

At the end of Phase 1 the `list/` folder contains fully populated text files enumerating every technique, group, tactic, and mitigation in the MITRE ATT&CK knowledge base, each paired with its canonical URL. Those files serve as the input manifest for Phase 2.

#### 5.2.2 Phase 2 — Scraping Page Content from Each URL

The second script, `link_scrape.py`, reads the link catalogue produced in Phase 1 and visits every individual URL to download and extract the human-readable content from that page. This is where the actual cybersecurity text that will eventually be embedded and indexed is collected.

**Step 1 — Parsing the link catalogue.** The function `parse_links_from_docs` reads a Phase 1 output file line by line. It expects the `ID - Name - URL` format but also implements a regex fallback that locates any HTTP URL anywhere in a line and derives the technique identifier from the URL path. This makes the parser tolerant of minor formatting variations.

```python
def parse_links_from_docs(path: str) -> List[Tuple[str, str]]:
    links = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("Source:") or line.startswith("Terms:"):
                continue
            parts = [p.strip() for p in line.split(" - ")]
            if len(parts) >= 3 and parts[2].startswith("http"):
                links.append((parts[0], parts[2]))          # (ID, URL)
            else:
                m = re.search(r"https?://\S+", line)
                if m:
                    url  = m.group(0)
                    tid  = derive_id_from_url(url)           # parse ID from path
                    links.append((tid, url))
    return links

def derive_id_from_url(url: str) -> str:
    # Handles /techniques/T1548/ and /techniques/T1548/001/
    m = re.search(r"/techniques/(T\d+)(?:/(\d{3})/?)?", url)
    if not m:
        return "unknown"
    base, sub = m.group(1), m.group(2)
    return f"{base}.{sub}" if sub else base
```

**Step 2 — Fetching each page.** For every `(technique_id, url)` pair produced by the parser, the `fetch_page` function issues an HTTP GET request with a browser-like `User-Agent` header to avoid being blocked. A 30-second timeout prevents the pipeline from stalling on unresponsive hosts.

```python
def fetch_page(url: str) -> str:
    resp = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (compatible; scraper/1.0)"},
    )
    resp.raise_for_status()
    return resp.text
```

**Step 3 — Extracting title and body text.** The `extract_title_and_paragraphs` function parses the raw HTML with BeautifulSoup and applies a two-level extraction strategy:

1. **Preferred path**: it looks for the CSS selector `.col-md-8 .description-body`, which is the main article container on MITRE ATT&CK pages. If found, the entire inner text is returned as a single block, preserving the complete description without truncation.
2. **Fallback path**: if the preferred container is absent, the function falls back to collecting all `<p>` tags found inside `<main>` (or the body root), filtering out cookie-banner noise.

```python
def extract_title_and_paragraphs(html: str) -> Tuple[str, List[str]]:
    soup = BeautifulSoup(html, "html.parser")

    # Title: prefer <h1>, fallback to <title>
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else soup.find("title").get_text(strip=True)

    # Preferred container — MITRE ATT&CK article body
    container = soup.select_one(".col-md-8 .description-body")
    if container:
        return title, [container.get_text(" ", strip=True)]

    # Fallback: collect <p> tags from the main content area
    main = soup.find("main") or soup.find("div", attrs={"role": "main"}) or soup
    paragraphs = []
    for p in main.find_all("p"):
        txt = p.get_text(" ", strip=True)
        if txt and not ("cookies" in txt.lower() and "privacy" in txt.lower()):
            paragraphs.append(txt)
    return title, paragraphs
```

**Step 4 — Saving the output.** The extracted content is written to a per-resource `.txt` file inside `backend/scraping/MITRE/techniques/` (or the equivalent sub-folder). Each file contains a small header block followed by the body text, normalized to remove redundant whitespace.

```python
def write_txt(technique_id, title, url, paragraphs, out_dir) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{technique_id}.txt")
    header = [
        f"ID: {technique_id}",
        f"Title: {title}",
        f"URL: {url}",
    ]
    body = " ".join(re.sub(r"\s+", " ", p).strip() for p in paragraphs) or "(no summary)"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(header) + "\n" + body + "\n")
    return path
```

**Step 5 — Orchestrating the full run.** The `run` function ties all steps together: it parses the link catalogue, iterates over every entry, fetches the page, extracts content, and writes the output file. Failures for individual pages are caught and logged without interrupting the rest of the run, so a single network error or missing page does not abort the entire collection job.

```python
def run(input_file: str, out_dir: str, limit: int = None):
    links = parse_links_from_docs(input_file)
    count = 0
    for technique_id, url in links:
        try:
            html      = fetch_page(url)
            title, paragraphs = extract_title_and_paragraphs(html)
            path      = write_txt(technique_id, title, url, paragraphs, out_dir)
            print(f"Saved: {path}")
            count += 1
            if limit and count >= limit:
                break
        except Exception as e:
            print(f"Failed for {technique_id} {url}: {e}")
    print(f"Total saved: {count}")
```

The script is also exposed as a command-line tool, allowing the input file, output directory, and page limit to be overridden without editing the source:

```bash
python link_scrape.py --input list/mitre_enterprise_techniques.txt \
                      --out   MITRE/techniques \
                      --limit 50
```

#### 5.2.3 End-to-End Summary

The complete two-phase scraping pipeline can be summarized as follows:

1. Run `mitre_list_scrape.py` → scrapes MITRE ATT&CK listing pages → writes `list/*.txt` files containing `ID - Name - URL` lines for every technique, group, tactic, and mitigation.
2. Run `link_scrape.py` for each list file → reads each URL → fetches the individual MITRE page → extracts the title and description body → writes a per-resource `.txt` file to `MITRE/techniques/` or `MITRE/groups/`.
3. The resulting `.txt` files in the `MITRE/` sub-folders are then treated as raw cybersecurity documents and fed into the preprocessing, chunking, and field-mapping pipeline described in sections 5.3, 5.4, and 5.5.

### 5.3 Preprocessing

Before documents can be indexed, they must be cleaned and normalized. The preprocessing pipeline (implemented in upload_doc.py and supporting modules) performs the following operations:

- Removing HTML tags, markup, or boilerplate that is not useful for semantic search.
- Stripping or normalizing code blocks and configuration snippets when they are not central to understanding the text, or marking them explicitly when they are useful examples.
- Unifying character encodings and normalizing whitespace.
- Extracting metadata such as document source, document type (e.g., "CVE description", "forum post", "guideline"), and publication date when available.

The output of this step is a set of clean text fields and metadata ready to be chunked and embedded.

### 5.4 Chunking and Embedding

Long documents are split into smaller, semantically coherent chunks so that Azure AI Search can retrieve only the most relevant segments for a given query. The chunking strategy is typically based on:

- Maximum token length or character length per chunk.
- Natural boundaries such as paragraphs, headings, or list items.

Each chunk is then converted into a dense vector representation using Azure OpenAI embeddings. In the implementation, the helper function get_openai_embedding in _utils.py calls the configured embedding deployment (EMBEDDING_DEPLOYMENT_NAME) to produce vectors. For batch operations, get_openai_embeddings_batch reduces the number of API round-trips by embedding multiple chunks at once.

The resulting vectors are stored in the Azure AI Search index alongside the original text and metadata. This enables hybrid search that combines vector similarity with traditional keyword filtering.

### 5.5 Field Mapping in Detail

Field mapping is the transformation stage that aligns the internal JSON document schema with the Azure AI Search index schema before document upload. In this project, the mapping is implemented in `map_documents_for_search` and functions as an explicit interface between preprocessing outputs and index-ingestion inputs.

The function defines a mapping dictionary in which each source key from the input document is associated with a target key required by the index payload. The default mapping is as follows:

| Source field | Target field |
|---|---|
| `id` | `id` |
| `content` | `content` |
| `contentVector` | `content_vector` |
| `source` | `source` |
| `category` | `category` |

Accordingly, the function reads values from the original document structure and rewrites them into the index-aligned structure. The mapping from `contentVector` to `content_vector` is a critical case because vector-field naming conventions in the index may differ from those used in upstream JSON files.

The transformation is implemented through a dictionary comprehension:

```python
doc_to_upload = {target: doc.get(source) for source, target in field_mapping.items()}
```

After transformation, the function applies a required-field validation step:

```python
if not all([
    doc_to_upload.get("id"),
    doc_to_upload.get("content"),
    doc_to_upload.get("content_vector"),
]):
    continue
```

Records that do not contain an identifier, content text, or embedding vector are excluded from upload. This filtering mechanism improves ingestion reliability by preventing incomplete or structurally invalid records from entering the search index.

From an engineering perspective, the field-mapping stage provides several benefits:

- Schema compatibility with Azure AI Search index definitions.
- Data quality control through early validation of mandatory attributes.
- Maintainability through centralized key-conversion logic.
- Extensibility through support for alternative schemas via `field_mapping` overrides.

In summary, field mapping is not merely a syntactic conversion step; it is a structural quality-control mechanism that preserves consistency between document-preparation outputs and index-ingestion requirements.

### 5.6 Summary

This chapter has highlighted how cybersecurity-specific documents are collected, cleaned, chunked, and embedded before indexing. Careful data preparation ensures that the retrieval-augmented generation pipeline can surface precise and contextually rich passages when users query the system about vulnerabilities, attack groups, or defensive measures.

### 5.7 Code Snippets

The ingestion and indexing pipeline is implemented with explicit loading, mapping, and upload stages.

```python
documents = load_json_documents_from_blob(blob_connection_string, CONTAINER_NAME)
logger.info(f"Loaded {len(documents)} documents")

doc_to_upload = map_documents_for_search(documents)
logger.info(f"Mapped {len(doc_to_upload)} documents for upload")

upload_documents_to_search(search_client, doc_to_upload)
```

```python
def map_documents_for_search(documents, field_mapping=None):
   if field_mapping is None:
      field_mapping = {
         "id": "id",
         "content": "content",
         "contentVector": "content_vector",
         "source": "source",
         "category": "category",
      }

   documents_to_upload = []
   for doc in documents:
      doc_to_upload = {target: doc.get(source) for source, target in field_mapping.items()}
      if not all([doc_to_upload.get("id"), doc_to_upload.get("content"), doc_to_upload.get("content_vector")]):
         continue
      documents_to_upload.append(doc_to_upload)
   return documents_to_upload
```

## Chapter 6: Application Implementation

### 6.1 Introduction

This chapter presents the implementation of the proposed cybersecurity question-answering system. The discussion focuses on how the design presented in earlier chapters is operationalized in software, with emphasis on backend orchestration, semantic retrieval, prompt construction, and frontend interaction. The objective is to document the implementation decisions that enable reliable, context-grounded responses in a production-oriented web architecture.

### 6.2 Backend Logic (Python)

#### 6.2.1 Connecting to Azure OpenAI

The backend integrates Azure OpenAI through the `AzureOpenAI` client provided by the `openai` Python package. To improve modularity and reduce configuration duplication, credential retrieval and model invocation are encapsulated in reusable utility functions in `backend/_utils.py`.

- `get_azure_openai_credentials` retrieves the endpoint and key for the Azure OpenAI resource through `CognitiveServicesManagementClient`.
- `get_openai_embedding` invokes the embeddings endpoint for query-vector generation.
- `get_openai_completion` invokes the chat completions endpoint for final answer generation.

These utilities are called by `backend/server.py` during request processing, thereby separating infrastructure-level concerns (credentials and endpoints) from application-level logic (retrieval and response construction).

#### 6.2.2 Search Algorithm (Hybrid Search)

The retrieval pipeline implements a hybrid search strategy that combines semantic matching and lexical fallback. This approach is designed to preserve robustness across heterogeneous cybersecurity queries, including queries with technical identifiers, abbreviations, and domain-specific terminology.

The retrieval workflow is implemented as follows:

1. The user question is embedded via get_openai_embedding.
2. The embedding vector is sent to `search_index` (`backend/search_query/search_query.py`) to perform vector retrieval against Azure AI Search.
3. Returned results are filtered by a similarity threshold (for example, approximately 0.55 to 0.60 depending on runtime configuration).
4. If no vector results satisfy the threshold, the backend performs a keyword-based search using the raw question text.
5. Retrieved passages and metadata are aggregated into a context block used for answer generation.

This design improves retrieval coverage: vector search captures semantic similarity, whereas keyword fallback mitigates cases in which exact lexical cues are more informative than embedding proximity.

#### 6.2.3 System Instructions and Persona

Prompt construction is implemented as a deterministic procedure rather than as ad hoc free-form prompting. The backend constructs the `messages` payload to enforce domain specialization, response grounding, and multi-turn continuity.

The procedure contains four components:

1. **System instruction (persona and constraints)**
    - The model is instructed to act as a cybersecurity specialist.
    - The model is constrained to answer from retrieved context rather than unsupported prior knowledge.
    - Link formatting is standardized in Markdown form.

2. **Conversation history injection**
    - Prior user and assistant turns from `sessions[session_id]` are appended to preserve conversational state.

3. **Grounded user-message template**
    - The incoming query is wrapped as `Context:\n{context}\n\nQuestion: {question}`.
    - This template explicitly conditions generation on retrieved evidence.

4. **Retrieval-to-prompt coupling**
    - Context is assembled from high-relevance search results using `content` and `source` fields.
    - Keyword fallback is applied when vector retrieval is insufficient, ensuring context availability prior to completion calls.

The core prompt-construction implementation in `server.py` is shown below:

```python
messages = [
   {
      "role": "system",
      "content": (
         "You are a cybersecurity specialist. Use the provided context to "
         "answer the user's question. Do not use your own database to answer!."
         "If there is a link attached to the answer, format it with markdown and put at the end of the sentence as [More info](link)."
      ),
   },
]

for msg in sessions[session_id]:
   messages.append(msg)

messages.append(
   {
      "role": "user",
      "content": f"Context:\n{context}\n\nQuestion: {question}",
   }
)
```

This implementation provides reproducibility and reduces unsupported outputs by enforcing a consistent retrieval-to-generation pathway.

### 6.3 Frontend Prototype

The frontend is implemented as a Vite + React single-page application that provides the user-facing conversational interface. Its role is to capture queries, display grounded responses, and manage local conversation state.

The primary implementation elements are:

- **Application composition**: `main.jsx` initializes the React root and renders `App.jsx`, which hosts `Chat.jsx` as the principal interactive view.
- **Chat orchestration**: `Chat.jsx` manages message state, input state, loading/error indicators, and session identifiers. It interacts with `client.js` for backend communication and with `sessions.js` for client-side persistence.
- **Response rendering**: `Message.jsx` renders assistant output through `ReactMarkdown` with `remark-gfm` and `rehype-highlight`, enabling structured responses (lists, tables, and code blocks).
- **Session management UI**: `SessionSidebar.jsx` supports session listing, loading, and deletion, thereby improving multi-turn usability.

Although lightweight in architecture, the frontend is functionally complete for prototype validation: it supports query submission, grounded response visualization, and iterative dialogue management.

### 6.4 Summary

This chapter has documented the software implementation of the proposed system. The backend integrates Azure OpenAI and Azure AI Search, executes a hybrid semantic retrieval process, and applies a structured prompt-construction strategy for context-grounded generation. The frontend operationalizes these services through a session-aware conversational interface. Together, these components implement the end-to-end RAG workflow defined in the system design.

### 6.5 Code Snippets

The following excerpts illustrate representative frontend implementation logic used in the prototype.

```jsx
const handleSend = async () => {
   const text = input.trim()
   if (!text || loading) return

   const nextMessages = [...messages, { role: 'user', content: text }]
   setMessages(nextMessages)

   const response = await sendMessage(text, sessionId)
   const newSessionId = response.session_id || sessionId
   setSessionId(newSessionId)
   setMessages([...nextMessages, { role: 'assistant', content: response.answer }])
}
```

```jsx
<ReactMarkdown
   remarkPlugins={[remarkGfm]}
   rehypePlugins={[rehypeHighlight]}
   components={{
      a: ({ node, ...props }) => (
         <a {...props} target="_blank" rel="noopener noreferrer" />
      ),
   }}
>
   {content}
</ReactMarkdown>
```

## Chapter 7: Testing and Evaluation

### 7.1 Introduction

This chapter outlines the testing and evaluation strategy for the system, including functional testing of automation scripts and application endpoints, qualitative assessment of search and answer quality, and baseline performance considerations such as latency and cost.

### 7.2 Functional Testing

Functional testing verifies that individual components behave as expected:

- Backend endpoints: The /health endpoint is used to confirm that the FastAPI server is running. The /api/new-session and /api/chat endpoints are tested with valid and invalid payloads (e.g., empty questions) to ensure correct error handling.
- Session persistence: Tests verify that sessions are created, updated, and saved correctly, and that the save-session endpoint writes valid JSON files into the frontend/sessions directory.
- Automation scripts: The deploy.py and upload_doc.py scripts are executed in a controlled environment to ensure that resources are created successfully and documents are ingested without errors.

### 7.3 Search and Answer Quality

To assess the quality of retrieval and generated answers, representative cybersecurity queries are issued and the responses are compared with the underlying documents.

An illustrative example is the query:

- "How do I mitigate the Log4j vulnerability?"

The expected behavior is that the system retrieves passages discussing Log4j, remote code execution risks, and mitigation strategies (e.g., upgrading affected libraries, applying vendor patches, and restricting outbound connections) and then generates a concise, actionable summary. The evaluation considers:

- Relevance: Do the retrieved chunks and the generated answer directly address the vulnerability and mitigation steps?
- Groundedness: Are claims in the answer supported by the retrieved context, or does the model introduce unsupported statements?
- Clarity: Is the answer structured in a way that a practitioner can easily follow (e.g., bullet-point mitigations, clear prioritization)?

Similar qualitative checks can be performed for other queries, such as "What are common ransomware attack vectors?" or "Describe the tactics of a specific MITRE ATT&CK group."

### 7.4 Performance and Cost Considerations

Performance evaluation considers both latency and expected cost:

- Latency: For each query, the end-to-end time from sending the request to receiving the answer is measured. This latency is primarily influenced by the embedding call, Azure AI Search query, and chat completion call. Caching strategies or batching could be introduced in future work if lower latency is required.
- Cost: The main cost drivers are Azure OpenAI token usage and Azure AI Search indexing and query operations. By using chunked documents and a moderate top-k value in search_index, the system limits the amount of context sent to the model, thereby controlling token costs. The choice of models (e.g., text-embedding-3-small and gpt-4o-mini) also reflects a trade-off between capability and price.

### 7.5 Summary

This chapter has described how the system is tested and evaluated. Functional tests verify the correctness of endpoints and automation scripts, qualitative assessments check the relevance and groundedness of answers to security-focused queries, and performance analysis provides an initial view of latency and cost. Together, these evaluations demonstrate that the system can deliver useful, context-aware cybersecurity assistance while remaining operationally feasible.
