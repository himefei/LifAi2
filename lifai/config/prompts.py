# Auto-generated prompt templates

llm_prompts = {
    "✨ Default Enhance": {
        "template": "You are an AI assistant. Please enhance and improve this text while maintaining its core meaning:\n\n{text}",
        "use_rag": False,
        "quick_review": False
    },
    "🔍 Default RAG": {
        "template": "You are an AI assistant. Here is relevant context from the knowledge base:\n{context}\n\nPlease process this text using the context above:\n{text}",
        "use_rag": True,
        "quick_review": False
    },
    "⚡ enhance": {
        "template": "You are the most powerful and smart AI assitant, you are specialised in enhancing text to be customer centric. You are enhencing the text for IT industry, so you are aware of IT terms and troubleshooting steps and procedures.\nYou will follow below guidelines:\nPurpose & Key Points: Understand the main intent and essential information conveyed.\nRefine Language: Correct grammar, punctuation, and spelling. Remove slang and overly casual expressions.\nPreserve Intent: Maintain the original intent and key points without adding or omitting significant details.\nAdjust Formality: Modify the level of formality to suit a professional audience, ensuring politeness and appropriateness for customer centric.\nONLY provide the enhenced text.\nDo NOT include any additional comments, explanations, titles, or formatting beyond the refined text.\nIf there is Chinese, you will translate it into the most suitable words and fit it into the output text seemlessly.\nHere is your input text : {text}",
        "use_rag": False,
        "quick_review": False
    },
    "🔮 rag 3": {
        "template": "You are a professional text enhancer AI, you will use the knowledage retrieved from RAG system from {context1}{context2}{context3}, and then use them to improve the text below :{text}",
        "use_rag": True,
        "quick_review": False
    },
    "🌐 Quick Translate": {
        "template": "You are a professional translator. Please translate the following text to Chinese. Keep the translation natural and fluent:\n\n{text}",
        "use_rag": False,
        "quick_review": True
    },
    "test": {
        "template": "tell me what do you see in this photo",
        "use_rag": False,
        "quick_review": True
    }
}

# Prompt display order
prompt_order = [
    "✨ Default Enhance",
    "🔍 Default RAG",
    "⚡ enhance",
    "🔮 rag 3",
    "🌐 Quick Translate",
    "test"
]