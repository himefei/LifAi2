import os

# Default prompts
default_prompts = {
    "Fix spelling and grammar": """Act as a professional editor. Review and correct any spelling mistakes, grammatical errors, and typos in the text below. Maintain the original meaning, tone, and style:

Text to correct:
{text}

Provide the corrected version only.""",
    
    "Improve writing quality": """Act as an expert writing coach. Enhance the following text to be more professional, concise, and impactful. Focus on:
- Improving clarity and flow
- Removing redundancy
- Strengthening word choice
- Maintaining the original message

Original text:
{text}

Provide the improved version only.""",
    
    "Make text more polite and friendly": """Act as a communication expert. Rewrite the following text to be more approachable and courteous while maintaining professionalism. The tone should be warm but not overly casual:

Original text:
{text}

Provide the polite version only.""",
    
    "Simplify text": """Act as a plain language expert. Rewrite the following text to be easily understood by a general audience. Use:
- Simple words and short sentences
- Clear structure
- Active voice
- Everyday language

Original text:
{text}

Provide the simplified version only.""",
    
    "Summarize": """Act as a professional summarizer. Create a clear, concise summary of the key points from the following text. The summary should be roughly 25% of the original length:

Text to summarize:
{text}

Provide the summary only.""",
    
    "Analyze and respond": """Act as an expert analyst. For the following text:
1. Identify the main points and underlying themes
2. Analyze the context and implications
3. Generate a relevant, thoughtful response

Text to analyze:
{text}

Provide your analysis and response in a clear, structured format.""",
    
    "Translate to Chinese": """Act as a professional translator. Translate the following text into Simplified Chinese (简体中文). Maintain the original meaning and tone while ensuring the translation is natural and culturally appropriate:

Text to translate:
{text}

Provide the Chinese translation only.""",
    
    "Translate to English": """Act as an expert linguist and professional translator with deep knowledge of cultural nuances and idiomatic expressions. Your task is to translate the following text into clear, natural-sounding English.

Guidelines for translation:
- Preserve the original meaning and intent
- Maintain the appropriate tone (formal/informal)
- Use culturally appropriate expressions
- Adapt idioms and metaphors naturally
- Ensure grammatical accuracy
- Retain any technical terminology with proper English equivalents

If you encounter:
- Ambiguous phrases: Choose the most contextually appropriate translation
- Cultural references: Provide equivalent English expressions when possible
- Technical terms: Maintain industry-standard terminology

Source text:
{text}

Instructions:
1. First, identify the source language (if not obvious)
2. Provide a high-quality English translation
3. Maintain any formatting or paragraph structure from the original

Provide the English translation only, without explanations or notes.""",

    "Call centre vibe": """You are the best tech support and call centre customer service person. You will first try to understand the text and what the customer's pain point from the inpu text, then rewrite the text with your customer service soft skill with empathy and try to address the pain points the customer has with your response.

Input text:
{text}

Provide only the rewrite version without your commonts.
When rewrite your response, make sure you are aware of the input text type. If it is an email format, you will response with an email. If it is a message, you will respond message. So on and so forth."""
}

# Try to load saved prompts, fall back to defaults if not found
saved_prompts_file = os.path.join(os.path.dirname(__file__), 'saved_prompts.py')
try:
    if os.path.exists(saved_prompts_file):
        namespace = {}
        with open(saved_prompts_file, 'r', encoding='utf-8') as f:
            exec(f.read(), namespace)
        llm_prompts = namespace.get('llm_prompts', default_prompts)
    else:
        llm_prompts = default_prompts.copy()
except Exception:
    llm_prompts = default_prompts.copy()

# Get options from llm_prompts keys
improvement_options = list(llm_prompts.keys())