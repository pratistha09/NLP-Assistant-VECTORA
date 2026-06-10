import re
import os
import json

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

def parse_invoice_locally(text):
    """
    Rule-based local parser using Regex and SpaCy.
    """
    global _spacy_nlp
    
    # 1. Initialize empty data structure
    data = {
        "invoice_number": "N/A",
        "date": "N/A",
        "vendor_name": "N/A",
        "client_name": "N/A",
        "total_amount": "N/A",
        "tax_amount": "N/A",
        "currency": "₹",
        "line_items": [],
        "mode": "Local Extraction (Offline)"
    }
    
    # 2. Extract Invoice Number
    inv_match = re.search(r'(?:INV|Invoice|Invoice\s*Number|Inv\s*#)[:#\s]*([A-Za-z0-9-]+)', text, re.IGNORECASE)
    if inv_match:
        data["invoice_number"] = inv_match.group(1).strip()
    else:
        # Check general INV-xxxx format
        inv_gen = re.findall(r'INV-\d+', text)
        if inv_gen:
            data["invoice_number"] = inv_gen[0]
            
    # 3. Extract Dates
    date_match = re.search(r'(?:Date|Invoice\s*Date|Dated)[:#\s]*([0-9a-zA-Z\s,/-]{6,20})', text, re.IGNORECASE)
    if date_match:
        data["date"] = date_match.group(1).strip()
    else:
        # Match any generic date
        date_gen = re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', text)
        if date_gen:
            data["date"] = date_gen[0]
            
    # 4. Currency detection
    if "$" in text:
        data["currency"] = "$"
    elif "€" in text:
        data["currency"] = "€"
    elif "£" in text:
        data["currency"] = "£"
        
    # 5. Extract Total Amount
    # Matches words like Total, Grand Total, Net Amount, Amount Due followed by money formats
    total_match = re.search(
        r'(?:Total|Grand\s*Total|Amount\s*Due|Net\s*Payable|Total\s*Due)[:#\s]*(?:₹|\$|€|£|INR|USD)?\s*([\d,]+(?:\.\d{2})?)', 
        text, 
        re.IGNORECASE
    )
    if total_match:
        data["total_amount"] = total_match.group(1).strip()
    else:
        # Regex search for any currency numbers at the end of lines or isolated
        amounts = re.findall(r'(?:₹|\$|€|£|INR|USD)\s*([\d,]+(?:\.\d{2})?)', text)
        if amounts:
            # Assume largest amount or last amount is total
            clean_amounts = []
            for a in amounts:
                try:
                    val = float(a.replace(",", ""))
                    clean_amounts.append((val, a))
                except ValueError:
                    pass
            if clean_amounts:
                clean_amounts.sort(key=lambda x: x[0])
                data["total_amount"] = clean_amounts[-1][1] # Largest is usually total
                
    # 6. Extract Tax Amount
    tax_match = re.search(r'(?:Tax|GST|VAT|CGST|SGST)[:#\s]*(?:₹|\$|€|£|INR|USD)?\s*([\d,]+(?:\.\d{2})?)', text, re.IGNORECASE)
    if tax_match:
        data["tax_amount"] = tax_match.group(1).strip()
        
    # 7. Extract Vendor & Client Name (Heuristics & SpaCy)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if lines:
        # Usually vendor name is in the first 3 lines
        data["vendor_name"] = lines[0]
        
    # Check for "Bill To" or "Client" or "To" for client name
    client_found = False
    for i, line in enumerate(lines):
        if re.search(r'(?:Bill\s*To|Client|Ship\s*To|To|Customer)[:#\s]*$', line, re.IGNORECASE):
            if i + 1 < len(lines):
                data["client_name"] = lines[i+1]
                client_found = True
                break
        # Match inline client
        client_inline = re.search(r'(?:Bill\s*To|Client|Ship\s*To|Customer)[:#\s]+([A-Za-z0-9\s,\.]+)', line, re.IGNORECASE)
        if client_inline:
            data["client_name"] = client_inline.group(1).strip()
            client_found = True
            break
            
    # Use SpaCy to refine vendor/client if available
    if spacy is not None and (data["vendor_name"] == "N/A" or data["client_name"] == "N/A"):
        try:
            if _spacy_nlp is None:
                _spacy_nlp = spacy.load("en_core_web_sm")
            doc = _spacy_nlp(text)
            orgs = [ent.text for ent in doc.ents if ent.label_ == "ORG"]
            if orgs:
                if data["vendor_name"] == "N/A" or data["vendor_name"] in lines[:2]:
                    data["vendor_name"] = orgs[0]
                if not client_found and len(orgs) > 1:
                    data["client_name"] = orgs[1]
        except Exception:
            pass

    # 8. Extract Line Items (Simple regex parser looking for description and numeric values)
    # E.g. "Software Development 1 ₹50,000" or "Item name 10.00 5.00"
    for line in lines:
        # Match description + quantity + price
        # E.g. "Web Development  2  25000  50000" or similar
        parts = re.split(r'\s{2,}', line) # Split on double spaces
        if len(parts) >= 2:
            # Check if any part looks like a price/number
            num_parts = []
            desc_parts = []
            for p in parts:
                clean_p = p.replace(",", "").replace("$", "").replace("₹", "").strip()
                if re.match(r'^\d+(?:\.\d+)?$', clean_p):
                    num_parts.append(p)
                else:
                    desc_parts.append(p)
            if desc_parts and len(num_parts) >= 1:
                description = " ".join(desc_parts)
                price = num_parts[-1]
                qty = num_parts[0] if len(num_parts) > 1 else "1"
                try:
                    total = str(float(qty.replace(",","")) * float(price.replace(",","")))
                except ValueError:
                    total = price
                # Avoid capturing summary totals
                if "total" not in description.lower():
                    data["line_items"].append({
                        "description": description,
                        "quantity": qty,
                        "unit_price": price,
                        "total": total
                    })
                    
    # If no line items extracted, create a generic item from the total
    if not data["line_items"] and data["total_amount"] != "N/A":
        data["line_items"].append({
            "description": "General Procurement Services",
            "quantity": "1",
            "unit_price": data["total_amount"],
            "total": data["total_amount"]
        })
        
    return data

def extract_invoice_data(file_source, api_key=None):
    """
    Extracts structured invoice information from either a text string or a PDF file path.
    """
    text = ""
    is_file = False
    
    if os.path.exists(file_source):
        is_file = True
        if file_source.lower().endswith(".pdf"):
            text = extract_text_from_pdf(file_source)
        else:
            try:
                with open(file_source, "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception as e:
                text = f"[Error reading text file: {str(e)}]"
    else:
        text = file_source

    if not text or not text.strip() or text.startswith("[Error"):
        return {
            "invoice_number": "N/A",
            "date": "N/A",
            "vendor_name": "N/A",
            "client_name": "N/A",
            "total_amount": "N/A",
            "tax_amount": "N/A",
            "currency": "₹",
            "line_items": [],
            "mode": "Error / Empty Input"
        }

    # 1. Gemini API Mode (If key is provided)
    if api_key and genai is not None:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"""
            Analyze the following Invoice text and extract key metadata.
            Invoice text:
            \"\"\"{text}\"\"\"

            Provide your extraction in JSON format exactly as follows:
            {{
              "invoice_number": "String",
              "date": "String (e.g., YYYY-MM-DD)",
              "vendor_name": "String",
              "client_name": "String",
              "total_amount": "String (e.g., 50,000)",
              "tax_amount": "String (e.g., 9,000)",
              "currency": "String (e.g. ₹ or $ or €)",
              "line_items": [
                {{
                  "description": "String",
                  "quantity": "String",
                  "unit_price": "String",
                  "total": "String"
                }}
              ]
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
            data["mode"] = "Gemini AI OCR"
            return data
        except Exception as e:
            # Fallback to local
            pass

    # 2. Local/Offline Fallback Mode
    return parse_invoice_locally(text)

if __name__ == "__main__":
    sample = """
    ABC Technologies
    Sector 62, Noida, UP
    
    Invoice to:
    XYZ Solutions Pvt Ltd
    Connaught Place, New Delhi
    
    INVOICE NUMBER: INV-2026-998
    DATE: 05 June 2026
    
    Description                  Qty      Rate       Amount
    -------------------------------------------------------
    Software Development Services  1      ₹40,000     ₹40,000
    Cloud Server Hosting Setup    1      ₹10,000     ₹10,000
    -------------------------------------------------------
    Tax (18% GST):                           ₹9,000
    TOTAL AMOUNT:                            ₹59,000
    """
    
    print(extract_invoice_data(sample))