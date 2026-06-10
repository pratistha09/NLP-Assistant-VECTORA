import json
import re

# Try to import google-generativeai and transformers
try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from transformers import pipeline
    # Load sentiment analysis model lazily to save startup time
    _sentiment_pipeline = None
except ImportError:
    pipeline = None
    _sentiment_pipeline = None

def get_local_sentiment(text):
    """
    Analyzes sentiment locally. Tries Hugging Face pipeline, falls back to keyword analysis.
    """
    global _sentiment_pipeline
    text_lower = text.lower()
    
    # Simple keyword lexicon fallback
    positive_words = {"thank", "thanks", "great", "excellent", "good", "satisfied", "prompt", "resolved", "appreciate", "happy"}
    negative_words = {"disappointed", "poor", "slow", "delay", "late", "error", "fail", "issue", "problem", "wrong", "defect", "bad", "unacceptable"}
    
    pos_count = sum(1 for word in positive_words if word in text_lower)
    neg_count = sum(1 for word in negative_words if word in text_lower)
    
    if pos_count > neg_count:
        score = 70.0 + (pos_count - neg_count) * 5.0
        sentiment = "Positive"
    elif neg_count > pos_count:
        score = 70.0 + (neg_count - pos_count) * 5.0
        sentiment = "Negative"
    else:
        score = 50.0
        sentiment = "Neutral"
    score = min(score, 99.0)

    # Attempt to use Hugging Face transformers if available
    if pipeline is not None:
        try:
            if _sentiment_pipeline is None:
                # Using tiny model to run fast locally
                _sentiment_pipeline = pipeline(
                    "sentiment-analysis", 
                    model="distilbert-base-uncased-finetuned-sst-2-english",
                    device=-1  # Run on CPU
                )
            result = _sentiment_pipeline(text[:512]) # Truncate for safety
            label = result[0]["label"].capitalize()
            # Convert label
            if label == "Positive" or label == "Negative":
                sentiment = label
            confidence = round(result[0]["score"] * 100, 2)
            return sentiment, confidence, "Local NLP Model"
        except Exception:
            # Fail silently and use keyword heuristics
            pass
            
    return sentiment, score, "Local Heuristics (Offline)"

def rule_based_extract(text):
    """
    Extracts category, priority, action items, and dates using rules.
    """
    text_lower = text.lower()
    
    # 1. Category Classification
    category = "General Inquiry"
    if any(x in text_lower for x in ["payment", "pay", "charge", "refund", "remittance", "bank", "account"]):
        category = "Payment Issue"
    elif any(x in text_lower for x in ["invoice", "bill", "receipt", "statement", "inv-"]):
        category = "Invoice Query"
    elif any(x in text_lower for x in ["purchase", "order", "buy", "procure", "catalog", "quote", "rfp", "bid"]):
        category = "Purchase Request"
        
    # 2. Priority Classification
    priority = "Low"
    urgent_words = ["urgent", "immediate", "asap", "deadline", "important", "delay", "blocking", "late"]
    has_urgent = any(word in text_lower for word in urgent_words)
    if has_urgent or category == "Payment Issue":
        priority = "High"
    elif category in ["Invoice Query", "Purchase Request"] or len(text) > 200:
        priority = "Medium"
        
    # 3. Action Items Extraction
    sentences = re.split(r'[.!?\n]', text)
    action_items = []
    action_markers = ["please", "need", "send", "require", "submit", "request", "review", "provide", "update", "check"]
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        sentence_lower = sentence.lower()
        if any(marker in sentence_lower for marker in action_markers):
            # Clean punctuation
            clean_sent = re.sub(r'^\s*-\s*', '', sentence)
            if clean_sent and len(clean_sent) > 5:
                action_items.append(clean_sent)
                
    # 4. Key Dates Extraction
    # Matches formats: YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, and month names like "5 June 2026", "June 5th"
    date_patterns = [
        r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b',
        r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b',
        r'\b\d{1,2}?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b',
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4}\b'
    ]
    key_dates = []
    for pattern in date_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if match not in key_dates:
                key_dates.append(match)
                
    return category, priority, action_items, key_dates

def analyze_email_procurement(text, api_key=None):
    """
    Main entrypoint for analyzing procurement emails.
    """
    if not text or not text.strip():
        return {
            "sentiment": "Neutral",
            "category": "General Inquiry",
            "priority": "Low",
            "confidence": 0.0,
            "action_items": [],
            "key_dates": [],
            "explanation": "No text provided.",
            "mode": "Offline"
        }
        
    # 1. Gemini API Mode (If key is provided)
    if api_key and genai is not None:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"""
            Analyze the following email in a procurement/invoice/vendor context.
            Email text:
            \"\"\"{text}\"\"\"

            Provide your analysis in JSON format exactly as follows:
            {{
              "sentiment": "Positive" | "Negative" | "Neutral",
              "category": "Payment Issue" | "Invoice Query" | "Purchase Request" | "General Inquiry",
              "priority": "High" | "Medium" | "Low",
              "confidence": 0.0 to 100.0,
              "action_items": ["Action item 1", "Action item 2"],
              "key_dates": ["date references from text"],
              "explanation": "Brief explanation of the analysis"
            }}
            Do not include any markdown backticks or extra text. Output raw JSON.
            """
            response = model.generate_content(prompt)
            clean_text = response.text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            data = json.loads(clean_text.strip())
            data["mode"] = "Gemini AI"
            return data
        except Exception as e:
            # Fall back to local models if Gemini API fails
            pass

    # 2. Local/Offline Fallback Mode
    sentiment, confidence, mode = get_local_sentiment(text)
    category, priority, action_items, key_dates = rule_based_extract(text)
    
    explanation = f"Analyzed using local heuristics. Sentiment detected as {sentiment} with {confidence}% confidence."
    if "Local NLP Model" in mode:
        explanation = f"Analyzed using local Transformers model. Sentiment detected as {sentiment}."
        
    return {
        "sentiment": sentiment,
        "category": category,
        "priority": priority,
        "confidence": confidence,
        "action_items": action_items,
        "key_dates": key_dates,
        "explanation": explanation,
        "mode": mode
    }

if __name__ == "__main__":
    sample = "Hi Procurement, We are disappointed with the service. Invoice INV-1002 was submitted last Monday, 1 June 2026, but we haven't received payment yet. Please resolve this ASAP."
    print(analyze_email_procurement(sample))