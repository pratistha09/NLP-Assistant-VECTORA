import re
import os
import json
from collections import Counter

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    import spacy
    _spacy_nlp = None
except ImportError:
    spacy = None
    _spacy_nlp = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

def extract_text_from_pdf(pdf_path):
    """
    Extracts text from a PDF file using pdfplumber.
    """
    if pdfplumber is None:
        return "[Error: pdfplumber is not installed]"
    
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        text = f"[Error reading PDF: {str(e)}]"
    return text

def calculate_word_frequencies(text):
    """
    Helper to calculate normalized word frequencies, excluding common stopwords.
    """
    stopwords = {
        'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', "you're", "you've", "you'll", "you'd",
        'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', "she's", 'her', 'hers',
        'herself', 'it', "it's", 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which',
        'who', 'whom', 'this', 'that', "that'll", 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if',
        'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between',
        'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out',
        'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why',
        'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
        'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 'don', "don't", 'should',
        "should've", 'now', 'd', 'll', 'm', 'o', 're', 've', 'y', 'ain', 'aren', "aren't", 'couldn', "couldn't",
        'didn', "didn't", 'doesn', "doesn't", 'hadn', "hadn't", 'hasn', "hasn't", 'haven', "haven't", 'isn', "isn't",
        'ma', 'mightn', "mightn't", 'mustn', "mustn't", 'needn', "needn't", 'shan', "shan't", 'shouldn', "shouldn't",
        'wasn', "wasn't", 'weren', "weren't", 'won', "won't", 'wouldn', "wouldn't"
    }
    
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    filtered_words = [word for word in words if word not in stopwords]
    
    frequencies = Counter(filtered_words)
    if not frequencies:
        return {}
        
    max_freq = max(frequencies.values())
    for word in frequencies:
        frequencies[word] = frequencies[word] / max_freq
        
    return frequencies

def summarize_contract_locally(text):
    """
    Fast, offline extractive summarizer that scores sentences based on word frequencies.
    Also extracts key clauses (Parties, Duration, Financials, Scope, Risks).
    """
    global _spacy_nlp
    
    # 1. Clean input
    text_clean = re.sub(r'\s+', ' ', text).strip()
    
    # 2. Split into sentences
    sentences = []
    if spacy is not None:
        try:
            if _spacy_nlp is None:
                _spacy_nlp = spacy.load("en_core_web_sm")
            doc = _spacy_nlp(text_clean)
            sentences = [sent.text.strip() for sent in doc.sents]
        except Exception:
            pass
            
    if not sentences:
        # Regex splitter fallback
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text_clean) if s.strip()]
        
    if not sentences:
        return {
            "summary_text": "No valid text content found to summarize.",
            "clauses": {},
            "mode": "Offline Heuristics"
        }
        
    # 3. Score sentences
    freq_dict = calculate_word_frequencies(text_clean)
    sentence_scores = {}
    
    for sent in sentences:
        words = re.findall(r'\b[a-zA-Z]{3,}\b', sent.lower())
        score = sum(freq_dict.get(word, 0) for word in words)
        # Normalize score by length to avoid bias towards long sentences
        if len(words) > 0:
            sentence_scores[sent] = score / len(words)
        else:
            sentence_scores[sent] = 0
            
    # 4. Extract Top Sentences for general summary
    # Sort and pick top sentences (e.g., 20% of original, max 5, min 2)
    num_sentences = max(2, min(5, len(sentences) // 5))
    top_sentences = sorted(sentence_scores.items(), key=lambda x: x[1], reverse=True)[:num_sentences]
    
    # Sort top sentences back into original order of appearance
    original_order_summary = []
    for sent in sentences:
        if sent in dict(top_sentences):
            original_order_summary.append(sent)
            
    summary_text = " ".join(original_order_summary)
    
    # 5. Extract structured key clauses using pattern matching
    clauses = {
        "Parties Involved": [],
        "Duration & Effective Date": [],
        "Financial Obligations": [],
        "Scope of Services": [],
        "Termination & Dispute Resolution": []
    }
    
    for sent in sentences:
        sent_lower = sent.lower()
        
        # Parties Involved
        if any(x in sent_lower for x in ["agree", "between", "agreement is entered", "by and between", "referred to as", "parties"]):
            if len(sent) < 150 and sent not in clauses["Parties Involved"]:
                clauses["Parties Involved"].append(sent)
                
        # Duration & Effective Date
        if any(x in sent_lower for x in ["period of", "effective date", "duration", "shall commence", "terminate on", "months", "years"]):
            if sent not in clauses["Duration & Effective Date"]:
                clauses["Duration & Effective Date"].append(sent)
                
        # Financial Obligations
        if any(x in sent_lower for x in ["payment", "fee", "cost", "sum of", "value", "price", "invoice", "₹", "$", "charge"]):
            if sent not in clauses["Financial Obligations"]:
                clauses["Financial Obligations"].append(sent)
                
        # Scope of Services
        if any(x in sent_lower for x in ["service", "provide", "deliver", "obligation", "responsibility", "maintenance", "task"]):
            if sent not in clauses["Scope of Services"]:
                clauses["Scope of Services"].append(sent)
                
        # Termination & Dispute
        if any(x in sent_lower for x in ["terminate", "termination", "dispute", "arbitration", "jurisdiction", "breach", "liability"]):
            if sent not in clauses["Termination & Dispute Resolution"]:
                clauses["Termination & Dispute Resolution"].append(sent)
                
    # Format clauses: take top 2 lines for each clause to avoid clutter
    for key in clauses:
        clauses[key] = clauses[key][:2]
        if not clauses[key]:
            clauses[key] = ["No specific clause details extracted."]
            
    return {
        "summary_text": summary_text,
        "clauses": clauses,
        "mode": "Offline Heuristics"
    }

def summarize_contract(file_source, api_key=None):
    """
    Main entrypoint for contract summarization.
    Supports either text content or a PDF path.
    """
    text = ""
    if os.path.exists(file_source):
        if file_source.lower().endswith(".pdf"):
            text = extract_text_from_pdf(file_source)
        else:
            try:
                with open(file_source, "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception as e:
                text = f"[Error reading file: {str(e)}]"
    else:
        text = file_source

    if not text or not text.strip() or text.startswith("[Error"):
        return {
            "summary_text": "No contract text found.",
            "clauses": {},
            "mode": "Error / Empty Input"
        }

    # 1. Gemini Mode
    if api_key and genai is not None:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"""
            Analyze the following contract document and summarize it.
            Contract Text:
            \"\"\"{text}\"\"\"

            Provide your summary in JSON format exactly as follows:
            {{
              "summary_text": "A cohesive paragraph of about 3-5 sentences summarizing the core contract.",
              "clauses": {{
                "Parties Involved": ["Summary of parties details"],
                "Duration & Effective Date": ["Details about starting, duration, and end dates"],
                "Financial Obligations": ["Details of contract value, payments, schedules"],
                "Scope of Services": ["Details of what work/services are being provided"],
                "Termination & Dispute Resolution": ["Rules around contract termination, liabilities and arbitration"]
              }}
            }}
            Do not include any markdown backticks or extra text, output raw JSON.
            """
            response = model.generate_content(prompt)
            clean_text = response.text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            data = json.loads(clean_text.strip())
            data["mode"] = "Gemini AI Summarizer"
            return data
        except Exception:
            # Fallback to local
            pass
            
    # 2. Local Mode
    return summarize_contract_locally(text)

if __name__ == "__main__":
    sample = """
    SERVICE AGREEMENT
    This Agreement is made on 5 June 2026 between ABC Technologies (Vendor) and XYZ Solutions (Client).
    The Vendor shall provide Software Development services, including frontend development and system integration.
    The client agrees to pay a total contract value of ₹15,00,000 in monthly installments.
    The duration of this contract is 24 months, starting from the effective date.
    Either party may terminate this agreement with a 30-day written notice if a breach occurs.
    Any disputes will be resolved through arbitration in New Delhi.
    """
    print(summarize_contract(sample))