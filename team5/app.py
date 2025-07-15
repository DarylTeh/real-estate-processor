import streamlit as st
import boto3
import os
from dotenv import load_dotenv
from pathlib import Path
import uuid

# Load environment variables from .env if present
load_dotenv()

# AWS Configuration from env (used for Bedrock Agent and S3 config)
aws_region = os.getenv("AWS_DEFAULT_REGION", "us-west-2").strip()
agent_id = os.getenv("BEDROCK_AGENT_ID", "").strip()
agent_alias_id = os.getenv("BEDROCK_AGENT_ALIAS_ID", "").strip()
bucket_name = os.getenv("S3_BUCKET_NAME", "").strip()

# Initialize AWS session using default credential chain (IAM role, AWS CLI, etc.)
session = boto3.Session(region_name=aws_region)

# AWS clients
s3 = session.client("s3")
bedrock_runtime = session.client("bedrock-agent-runtime")


# 🔎 Check AWS credentials before continuing
def test_aws_connection():
    try:
        s3.list_buckets()
        return True, "AWS credentials are valid ✅"
    except Exception as e:
        return False, f"AWS credentials error: {str(e)}"


# ⬆️ Upload file to S3
def upload_to_s3(file, classification):
    folder = classification.replace(" ", "_").lower()
    filename = f"{folder}/{uuid.uuid4()}_{file.name}"
    s3.upload_fileobj(file, bucket_name, filename)
    return filename


# 🧠 Classify document using Bedrock Agent with strict validation
def classify_document(file):
    file_content = file.read()
    file.seek(0)

    prompt = f"""
You are a strict document classifier for real estate documents. You MUST classify this document into EXACTLY one of these 3 categories:

1. Settlement Documents
2. Income Verifications  
3. Purchase Agreements

IMPORTANT RULES:
- If the document has any of the categories listed inside as text, immediately classify it as one of the 3 categories
- Respond with ONLY the exact category name from the list above
- If the document does not clearly fit into any of these 3 categories, respond with: "INVALID_DOCUMENT"
- If the document is corrupted, unreadable, or not a real estate document, respond with: "INVALID_DOCUMENT"
- Do not provide explanations, descriptions, or any other text
- Do not create new categories

Document Content:
{file_content[:3000].decode(errors='ignore')}  # Limit to first 3000 characters
"""

    try:
        # Add progress indicator
        with st.spinner(f'🤖 Analyzing {file.name} with Bedrock Agent...'):
            response = bedrock_runtime.invoke_agent(
                agentId=agent_id,
                agentAliasId=agent_alias_id,
                sessionId=str(uuid.uuid4()),
                inputText=prompt
            )

        if 'completion' in response:
            completion = response['completion']
            if isinstance(completion, dict):
                result = completion.get('content', '').strip()
            else:
                output = ""
                for event in completion:
                    if 'chunk' in event and 'bytes' in event['chunk']:
                        output += event['chunk']['bytes'].decode('utf-8')
                result = output.strip()
            
            # Strict validation - only allow exact matches
            valid_categories = [
                "Settlement Documents",
                "Income Verifications", 
                "Purchase Agreements"
            ]
            
            # Clean up the result
            cleaned_result = result.strip()
            
            # Check for exact match first
            if cleaned_result in valid_categories:
                return cleaned_result
            
            # Check for partial matches (case insensitive)
            for category in valid_categories:
                if category.lower() in cleaned_result.lower():
                    return category
            
            # If no valid category found, mark as invalid
            return "INVALID_DOCUMENT"
        else:
            return "INVALID_DOCUMENT"

    except Exception as e:
        st.error(f"Error calling Bedrock Agent: {str(e)}")
        return "INVALID_DOCUMENT"


# 🌐 Streamlit UI
st.set_page_config(page_title="Real Estate Document Classifier", layout="wide")
st.title("🏡 Real Estate Document Classifier (AWS Bedrock + S3)")

# ✅ Credential check before allowing uploads
is_connected, connection_msg = test_aws_connection()
if is_connected:
    st.success(connection_msg)
else:
    st.error(connection_msg)
    st.stop()

uploaded_files = st.file_uploader(
    "📁 Upload multiple documents",
    type=["pdf", "png", "jpg", "jpeg", "docx", "txt"],
    accept_multiple_files=True
)

if uploaded_files:
    st.info("🔍 Classifying documents...")
    
    # Track results
    successful_uploads = 0
    failed_uploads = 0
    
    for file in uploaded_files:
        st.markdown(f"#### 📄 {file.name}")
        classification = classify_document(file)

        # Check if classification is valid (one of the 3 categories)
        valid_categories = ["Settlement Documents", "Income Verifications", "Purchase Agreements"]
        
        if classification in valid_categories:
            st.success(f"✅ Classified as: `{classification}`")
            file.seek(0)  # Reset for upload
            s3_path = upload_to_s3(file, classification)
            st.write(f"☁️ Uploaded to S3: `s3://{bucket_name}/{s3_path}`")
            successful_uploads += 1
        elif classification == "INVALID_DOCUMENT":
            st.error(f"❌ Document rejected: This file does not match any of the required real estate document categories (Settlement Documents, Income Verifications, Purchase Agreements)")
            st.warning("⚠️ File was not uploaded to S3")
            failed_uploads += 1
        else:
            # Fallback for any other response
            st.error(f"❌ Classification failed: Unable to properly classify this document")
            st.warning("⚠️ File was not uploaded to S3")
            failed_uploads += 1
    
    # Show summary
    st.markdown("---")
    st.markdown("### 📊 Upload Summary")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("✅ Successfully Uploaded", successful_uploads)
    with col2:
        st.metric("❌ Rejected Files", failed_uploads)
