llm_prompts = {
    "Pro spell fix": """Act as a professional editor. Review and correct any spelling mistakes, grammatical errors, and typos in the text below. Maintain the original meaning, tone, and style. Below is the input text : {text}
Output the corrected version only.""",
    "Pro rewrite": """You are a professional writer. You will first read and have a deep understand of the input text, then, enhance the input text to be more professional, concise, and impactful to used in a corporate formal communication. You will only provide the rewrited text wihtout any comments. Here is the input text : {text}""",
    "Pro summarize": """You are a professional summarizer. You will first read and gain a deep understanding of the input text, then, create a clear, concise summary of the key points. You will output a short summary in a bullet-point format. You will only output the summary withou any of your comments. Below is your input text: {text}""",
    "Pro CC response": """You are the best customer service person in a call centre. You will first read and gain a deep understand of customer needs as well as their pain points, use your soft skill to write a empathetic response to the customer. Your goal is to de-escalate the situation and try facilitate the customer's collaborations. Try using effective but easy to understand words. Only output the response without your comments. Here is your input text: {text}""",
}

# Get options from llm_prompts keys
improvement_options = list(llm_prompts.keys())
