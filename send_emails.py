import os
import base64
import time
import pandas as pd
from email.message import EmailMessage

from gmail_auth import get_gmail_service
from generate_emails import format_email_body

def send_approved_emails(output_file: str = "generated_emails.csv", resume_file: str = "resume.pdf", delay: float = 2.0, dry_run: bool = False):
    """
    Sends all approved generated emails via Gmail API with resume.pdf attached.
    """
    if not os.path.exists(output_file):
        print(f"File {output_file} does not exist yet. Run generation first.")
        return
        
    if not os.path.exists(resume_file) or os.path.getsize(resume_file) == 0:
        print(f"File {resume_file} not found or empty. Please ensure valid resume PDF exists.")
        return

    # Load dataframe cleanly with string dtype handling
    df = pd.read_csv(output_file)
    str_columns = ["Company", "Category", "Website", "Email", "target_role", "status", "approved", "generated_subject", "generated_body", "error_message"]
    for col in str_columns:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    to_send = df[(df['status'] == 'GENERATED') & (df['approved'].str.upper() == 'YES')]
    
    if to_send.empty:
        print("No approved emails ready for sending.")
        print("Ensure status is 'GENERATED' and approved is 'YES'.")
        return

    print(f"Found {len(to_send)} approved email(s) ready to send.")
    if dry_run:
        print("[DRY-RUN MODE] Simulating email sending without invoking Gmail API...")

    # Authenticate via Gmail API if not dry-run
    service = None
    if not dry_run:
        print("Authenticating with Gmail API...")
        try:
            service = get_gmail_service()
        except Exception as e:
            print(f"Gmail Authentication failed: {e}")
            return
        
    # Read the resume PDF once into bytes
    with open(resume_file, "rb") as f:
        resume_bytes = f.read()

    sent_count = 0
    failed_count = 0
    skipped_count = 0

    for index, row in to_send.iterrows():
        company = row.get("Company", "Unknown")
        target_email = row.get("Email", "").strip()
        subject = row.get("generated_subject", "").strip()
        body = format_email_body(row.get("generated_body", "").strip())
        
        if not target_email or "@" not in target_email:
            print(f"Skipping {company} - Invalid or missing email address ('{target_email}').")
            df.at[index, "error_message"] = "Invalid email address"
            skipped_count += 1
            continue

        if not subject or not body:
            print(f"Skipping {company} - Missing generated subject or body.")
            skipped_count += 1
            continue

        print(f"Sending email to {company} ({target_email})...")
        
        if dry_run:
            print(f"  [DRY-RUN] Would send to {target_email} | Subject: {subject[:40]}...")
            sent_count += 1
            continue

        try:
            # Build MIME message
            msg = EmailMessage()
            msg['To'] = target_email
            msg['Subject'] = subject
            msg.set_content(body)
            
            # Attach resume
            msg.add_attachment(
                resume_bytes, 
                maintype='application', 
                subtype='pdf', 
                filename="Sarthak_Borse_Resume.pdf"
            )
            
            raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
            
            service.users().messages().send(
                userId='me', 
                body={'raw': raw_message}
            ).execute()
            
            df.at[index, "status"] = "SENT"
            df.at[index, "error_message"] = ""
            sent_count += 1
            print("  -> Sent successfully.")
            
        except Exception as e:
            err_msg = str(e)
            df.at[index, "status"] = "SEND_FAILED"
            df.at[index, "error_message"] = err_msg
            failed_count += 1
            print(f"  -> Failed to send to {company}: {err_msg}")
            
        # Save dataframe after each attempt
        df.to_csv(output_file, index=False)
        time.sleep(delay)

    print("\n--- BATCH SENDING SUMMARY ---")
    print(f"Total Eligible : {len(to_send)}")
    print(f"Sent           : {sent_count}")
    print(f"Failed         : {failed_count}")
    print(f"Skipped        : {skipped_count}")
    print(f"Updated status saved to {output_file}.")

def main():
    send_approved_emails()

if __name__ == "__main__":
    main()

