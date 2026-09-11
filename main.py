import os
import sys
import argparse
import pandas as pd

import generate_emails
import send_emails

def interactive_review(csv_file="generated_emails.csv"):
    """
    Terminal CLI tool for interactive review and approval of generated emails.
    Allows user to approve individually [y], approve all [a], skip [s], or edit text [e].
    """
    if not os.path.exists(csv_file):
        print(f"File {csv_file} does not exist.")
        return
        
    df = pd.read_csv(csv_file)
    str_columns = ["Company", "Category", "Website", "Email", "target_role", "status", "approved", "generated_subject", "generated_body", "error_message"]
    for col in str_columns:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    pending_mask = (df['status'] == 'GENERATED') & (df['approved'].str.upper() != 'YES')
    pending_indices = df[pending_mask].index.tolist()

    if not pending_indices:
        print("No emails are awaiting review.")
        return

    print(f"\n==================================================")
    print(f" INTERACTIVE EMAIL REVIEW ({len(pending_indices)} pending)")
    print(f"==================================================\n")

    auto_approve_rest = False

    for idx in pending_indices:
        row = df.loc[idx]
        company = row.get("Company", "Unknown")
        role = row.get("target_role", "")
        email_to = row.get("Email", "")
        subject = row.get("generated_subject", "")
        body = row.get("generated_body", "")

        print("=" * 60)
        print(f"Company : {company}")
        print(f"Role    : {role}")
        print(f"Email To: {email_to}")
        print("-" * 60)
        print(f"SUBJECT : {subject}")
        print("-" * 60)
        print(f"{body}")
        print("=" * 60)

        if auto_approve_rest:
            df.at[idx, "approved"] = "YES"
            print(" -> Auto-approved!")
            continue

        while True:
            choice = input("\nAction: [y] Approve | [a] Approve All | [s] Skip | [e] Edit subject/body: ").strip().lower()
            if choice == 'y':
                df.at[idx, "approved"] = "YES"
                print(" -> Approved!")
                break
            elif choice == 'a':
                df.at[idx, "approved"] = "YES"
                auto_approve_rest = True
                print(" -> Approved this and all remaining!")
                break
            elif choice == 's':
                print(" -> Skipped.")
                break
            elif choice == 'e':
                new_sub = input(f"New Subject (press Enter to keep '{subject}'): ").strip()
                if new_sub:
                    df.at[idx, "generated_subject"] = new_sub
                print("Enter new body text (end input with CTRL+Z on Windows or empty line):")
                new_body = input("New Body (press Enter to keep current): ").strip()
                if new_body:
                    df.at[idx, "generated_body"] = new_body
                df.at[idx, "approved"] = "YES"
                print(" -> Updated and Approved!")
                break
            else:
                print("Invalid choice. Please enter y, a, s, or e.")

        df.to_csv(csv_file, index=False)

    print(f"\nReview session complete. Updated dataframe saved to {csv_file}.")

def auto_approve_all(csv_file="generated_emails.csv"):
    """
    Automatically approves all generated emails.
    """
    if not os.path.exists(csv_file):
        return
    df = pd.read_csv(csv_file)
    str_columns = ["Company", "Category", "Website", "Email", "target_role", "status", "approved", "generated_subject", "generated_body", "error_message"]
    for col in str_columns:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    gen_mask = (df['status'] == 'GENERATED')
    df.loc[gen_mask, 'approved'] = 'YES'
    df.to_csv(csv_file, index=False)
    print(f"Auto-approved {gen_mask.sum()} generated email(s).")

def main():
    parser = argparse.ArgumentParser(description="Internship Application Email Automation System")
    parser.add_argument("--mode", choices=["auto", "interactive", "generate", "send"], default="auto",
                        help="Execution mode: 'auto' (generate, approve, send), 'interactive' (terminal review), 'generate', or 'send'")
    parser.add_argument("--dry-run", action="store_true", help="Simulate email sending without sending via Gmail API")
    parser.add_argument("--retry-failed", action="store_true", help="Retry failed email generations or sends")
    
    args = parser.parse_args()

    print("==================================================")
    print(" INTERNSHIP APPLICATION EMAIL AUTOMATION SYSTEM   ")
    print("==================================================")
    print(f"Mode: {args.mode.upper()} | Dry-Run: {args.dry_run} | Retry Failed: {args.retry_failed}\n")

    if args.mode == "generate":
        generate_emails.main(retry_failed=args.retry_failed)
    elif args.mode == "send":
        send_emails.send_approved_emails(dry_run=args.dry_run)
    elif args.mode == "interactive":
        generate_emails.main(retry_failed=args.retry_failed)
        interactive_review()
        send_emails.send_approved_emails(dry_run=args.dry_run)
    elif args.mode == "auto":
        print("--- STAGE 1: Generating Emails ---")
        generate_emails.main(retry_failed=args.retry_failed)
        
        print("\n--- STAGE 2: Auto-Approving Emails ---")
        auto_approve_all()
        
        print("\n--- STAGE 3: Sending Approved Emails ---")
        send_emails.send_approved_emails(dry_run=args.dry_run)

    print("\nWorkflow completed successfully!")

if __name__ == "__main__":
    main()
