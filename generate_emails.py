import os
import pandas as pd
import pdfplumber
from google import genai
from google.genai import types
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY is not set in .env")

import time
import re

# Primary model and fallback list
PRIMARY_MODEL = 'models/gemini-3.8-flash'
FALLBACK_MODELS = ['models/gemini-3.5-flash-lite', 'gemini-3.8-flash']

client = genai.Client(api_key=API_KEY)

class EmailOutput(BaseModel):
    subject: str
    body: str

def get_target_role(category: str) -> str:
    if pd.isna(category):
        return "Technology Intern"
    cat_lower = str(category).lower()
    
    if "ai" in cat_lower or "ml" in cat_lower:
        return "AI/ML Intern"
    elif "data" in cat_lower or "analytics" in cat_lower:
        return "Data Analyst Intern"
    elif "software" in cat_lower or "it" in cat_lower:
        return "Software Engineering Intern"
    elif "saas" in cat_lower:
        return "Python / Software Intern"
    else:
        return "Technology Intern"

def extract_resume_text(pdf_path: str) -> str:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"{pdf_path} not found.")
    
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()

def get_candidate_profile(resume_text: str, cache_file: str = "candidate_profile.txt") -> str:
    """
    Extracts a concise candidate profile (~150-200 words) from resume text ONCE.
    Caches the output to save 85%+ prompt tokens across all company email generation requests.
    """
    if os.path.exists(cache_file) and os.path.getsize(cache_file) > 50:
        with open(cache_file, "r", encoding="utf-8") as f:
            print("Loaded cached candidate profile.")
            return f.read().strip()
            
    print("Generating concise candidate profile from resume (token optimization)...")
    prompt = f"""Summarize this candidate's resume into a compact candidate profile (approx 150-200 words).
Focus strictly on: Candidate Name, Education/Degree, Key Technical Skills, Top Projects, and Key Achievements.
Resume Text:
{resume_text}
"""

    for model in FALLBACK_MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )
            profile = response.text.strip()
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(profile)
            print("Successfully extracted and cached candidate profile.")
            return profile
        except Exception as e:
            print(f"Failed to generate profile with {model}: {e}")

    # Fallback to full resume text if profile generation fails
    print("Warning: Profile summarization failed; falling back to raw resume text.")
    return resume_text

def format_email_body(body: str) -> str:
    """
    Ensures email body has clean, professional paragraph spacing with proper double line breaks (\n\n).
    Fixes single-line text blobs and removes ugly unescaped strings.
    """
    if not body:
        return ""
    
    text = body.replace("\\n", "\n").replace("\r\n", "\n").strip()
    
    if "\n" in text:
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'^(Dear [^\n]+,)\s*\n?', r'\1\n\n', text, flags=re.IGNORECASE)
        text = re.sub(r'\n*(Sincerely,|Best regards,|Regards,|Thank you,)', r'\n\n\1', text, flags=re.IGNORECASE)
        return re.sub(r'\n{3,}', '\n\n', text).strip()
    
    # Single-line format fallback: insert proper paragraph breaks
    text = re.sub(r'^(Dear [^,.]+[\.,]?)\s*', r'\1\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*(Sincerely,|Best regards,|Regards,)\s*', r'\n\n\1\n', text, flags=re.IGNORECASE)
    parts = [p.strip() for p in text.split('\n') if p.strip()]
    
    formatted_paragraphs = []
    for p in parts:
        if re.match(r'^(Dear|Sincerely|Best regards|Regards)', p, re.IGNORECASE):
            formatted_paragraphs.append(p)
        else:
            sentences = re.split(r'(?<=\.)\s+', p)
            if len(sentences) > 2:
                mid = len(sentences) // 2
                p1 = ' '.join(sentences[:mid])
                p2 = ' '.join(sentences[mid:])
                formatted_paragraphs.extend([p1, p2])
            else:
                formatted_paragraphs.append(p)
                
    return '\n\n'.join(formatted_paragraphs)

def generate_email_for_company(candidate_profile: str, company: str, category: str, website: str, target_role: str):
    """
    Generates structured email (subject & body) using Gemini Structured JSON Outputs.
    Includes transient error retry with backoff and automatic paragraph formatting.
    """
    prompt = f"""You are writing a cold email requesting an internship opportunity.

Candidate Profile:
{candidate_profile}

Target Company Details:
- Company Name: {company}
- Industry/Category: {category}
- Website: {website}
- Role Applied For: {target_role}

Formatting & Content Rules:
1. Do not invent experiences/skills not listed in the candidate profile.
2. Do not claim the company is hiring; inquire politely if internship positions are available.
3. Length: 120-160 words. Tone: Professional, direct, enthusiastic, concise.
4. Avoid generic AI cliché phrasing.
5. Mention that the candidate's resume is attached to the email.
6. FORMAT REQUIREMENT: Separate salutation, body paragraphs, and sign-off with clear double newlines (\n\n). Do NOT return a single solid line of text.
"""

    for model in FALLBACK_MODELS:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=EmailOutput,
                    ),
                )
                if response.parsed:
                    formatted_body = format_email_body(response.parsed.body)
                    return response.parsed.subject.strip(), formatted_body, None
            except Exception as e:
                err_msg = str(e)
                print(f"  -> Model {model} attempt {attempt+1} failed for {company}: {err_msg[:120]}")
                time.sleep(2 ** attempt)
            
    return None, None, "Failed all model attempts for email generation."

def main(input_file="companies.csv", output_file="generated_emails.csv", resume_file="resume.pdf", retry_failed=False):
    # 1. Load data
    if os.path.exists(output_file):
        print(f"Loading existing {output_file}...")
        df = pd.read_csv(output_file)
    else:
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"{input_file} not found. Please create it.")
        print(f"Loading {input_file}...")
        df = pd.read_csv(input_file)
        
    # Ensure necessary columns exist and are string/object type to avoid pandas dtype issues
    required_cols = {
        "target_role": "",
        "status": "PENDING",
        "approved": "NO",
        "generated_subject": "",
        "generated_body": "",
        "error_message": ""
    }
    for col, default_val in required_cols.items():
        if col not in df.columns:
            df[col] = default_val
            
    # Fix pandas dtype 'float64' bug on string columns
    str_columns = ["Company", "Category", "Website", "Email", "target_role", "status", "approved", "generated_subject", "generated_body", "error_message"]
    for col in str_columns:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    # Compute missing target roles
    for index, row in df.iterrows():
        if not row["target_role"].strip():
            df.at[index, "target_role"] = get_target_role(row.get("Category", ""))

    # 2. Extract resume text & build condensed profile
    print("Reading resume...")
    resume_text = extract_resume_text(resume_file)
    candidate_profile = get_candidate_profile(resume_text)

    # 3. Filter rows to process
    target_statuses = ["PENDING"]
    if retry_failed:
        target_statuses.append("ERROR")

    # 4. Generate emails for target rows
    processed_count = 0
    for index, row in df.iterrows():
        current_status = row.get("status", "PENDING")
        if current_status in target_statuses:
            company = row.get("Company", "Unknown")
            print(f"Generating email for {company}...")
            
            subject, body, err = generate_email_for_company(
                candidate_profile=candidate_profile,
                company=company,
                category=row.get("Category", ""),
                website=row.get("Website", ""),
                target_role=row.get("target_role", "")
            )
            
            if subject and body:
                df.at[index, "generated_subject"] = subject
                df.at[index, "generated_body"] = body
                df.at[index, "status"] = "GENERATED"
                df.at[index, "error_message"] = ""
                processed_count += 1
                print(f"  -> Generated successfully.")
            else:
                df.at[index, "status"] = "ERROR"
                df.at[index, "error_message"] = err or "Generation failed"
                print(f"  -> Failed generation for {company}: {err}")
                
            # Save progress after each iteration
            df.to_csv(output_file, index=False)
            
    print(f"Done. Processed {processed_count} emails. Data saved to {output_file}.")

if __name__ == "__main__":
    main()

