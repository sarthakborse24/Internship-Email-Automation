import os
import pandas as pd

def main():
    output_file = "generated_emails.csv"
    
    if not os.path.exists(output_file):
        print(f"File {output_file} does not exist yet. Run generate_emails.py first.")
        return
        
    df = pd.read_csv(output_file)
    
    # Filter for emails that need review
    pending_review = df[(df['status'] == 'GENERATED') & (df['approved'] != 'YES')]
    
    if pending_review.empty:
        print("No emails are awaiting review.")
        return
        
    for index, row in pending_review.iterrows():
        print("="*60)
        print(f"Company : {row.get('Company')}")
        print(f"Role    : {row.get('target_role')}")
        print(f"Email To: {row.get('Email')}")
        print(f"Status  : {row.get('status')} | Approved: {row.get('approved')}")
        print("-" * 60)
        print(f"SUBJECT : {row.get('generated_subject')}")
        print("-" * 60)
        print(f"{row.get('generated_body')}")
        print("="*60)
        print("\n")
        
    print(f"Showing {len(pending_review)} emails awaiting review.")
    print("To approve, open generated_emails.csv and set the 'approved' column to 'YES'.")

if __name__ == "__main__":
    main()
