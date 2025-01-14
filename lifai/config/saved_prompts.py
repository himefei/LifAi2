llm_prompts = {
    "Default Enhance": {
        "template": """You are an AI assistant. Please enhance and improve this text while maintaining its core meaning:

{text}""",
        "use_rag": False
    },
    "Default RAG": {
        "template": """You are an AI assistant. Here is relevant context from the knowledge base:
{context}

Please process this text using the context above:
{text}""",
        "use_rag": True
    }
}

# Get options from llm_prompts keys
improvement_options = list(llm_prompts.keys()) 