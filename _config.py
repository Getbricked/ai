# Resource group settings
RG_NAME = "my-ai-ex-rg"
LOCATION = "eastus2"  # either eastus2 for text-embedding-3-small and gpt-4o-mini
# DELETE = True

# OpenAI settings
OPENAI_NAME = "myopenai-ex"
EMBEDDING_MODEL_NAME = "text-embedding-3-small"  # Model to deploy
EMBEDDING_DEPLOYMENT_NAME = "embedding-deploy"
GPT_MODEL_NAME = "gpt-4o-mini"
GPT_DEPLOYMENT_NAME = "gpt-deploy"

# Azure AI Search settings
SEARCH_NAME = "mysearch-ex"
INDEX_NAME = "my-text-index"

# Azure Storage settings
STORAGE_RG_NAME = "my-storage-rg"
STORAGE_NAME = "kbstorageex"  # Must be globally unique
CONTAINER_NAME = "documents"
