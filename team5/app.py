import streamlit as st
import boto3
import os
from dotenv import load_dotenv
from pathlib import Path
import uuid

# Load .env credentials
load_dotenv()

# AWS Configuration
aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
aws_region = os.getenv("AWS_DEFAULT_REGION")
agent_id = os.getenv("BEDROCK_AGENT_ID")
agent_alias_id = os.getenv("BEDROCK_AGENT_ALIAS_ID")
bucket_name = os.getenv("S3_BUCKET_NAME")
print(aws_access_key)
print(aws_secret_key)

if not all([aws_access_key, aws_secret_key, aws_region, agent_id, agent_alias_id, bucket_name]):
    raise RuntimeError("❌ Missing required AWS credentials or settings in .env. App cannot continue.")

# Initialize AWS clients
session = boto3.Session(
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
    region_name=aws_region
)

s3 = session.client("s3")
bedrock_runtime = session.client("bedrock-agent-runtime")


# Upload file to S3 based on classification
def upload_to_s3(file, classification):
    folder = classification.replace(" ", "_").lower()
    filename = f"{folder}/{uuid.uuid4()}_{file.name}"
    s3.upload_fileobj(file, bucket_name, filename)
    return filename


# Call Bedrock Agent to classify document
def classify_document(file):
    file_content = file.read()
    file.seek(0)

    prompt = f"""
You are a document classifier. Classify this document into one of the following categories:
1. Settlement Documents
2. Income Verifications
3. Purchase Agreements

Respond with only the category name.

Document Content:
{file_content[:3000].decode(errors='ignore')}  # Limit to first 3000 characters
"""
    try:
        response = bedrock_runtime.invoke_agent(
            agentId=agent_id,
            agentAliasId=agent_alias_id,
            sessionId=str(uuid.uuid4()),
            inputText=prompt
        )

        # The output structure depends on your Bedrock agent setup
        # If it's Claude or Titan model, adjust based on output schema
        messages = response.get("completion", {}).get("content", "")
        return messages.strip()

    except Exception as e:
        return f"Error: {str(e)}"


st.set_page_config(page_title="Real Estate Document Classifier", layout="wide")
st.title("🏡 Real Estate Document Classifier (AWS Bedrock + S3)")

uploaded_files = st.file_uploader("Upload multiple documents", type=["pdf", "png", "jpg", "jpeg", "docx", "txt"], accept_multiple_files=True)

if uploaded_files:
    st.info("Classifying documents...")

    for file in uploaded_files:
        st.markdown(f"#### 📄 {file.name}")
        classification = classify_document(file)

        if "Error" not in classification:
            st.success(f"✅ Classified as: `{classification}`")
            file.seek(0)  # Reset file pointer after read
            s3_path = upload_to_s3(file, classification)
            st.write(f"☁️ Uploaded to S3: `s3://{bucket_name}/{s3_path}`")
        else:
            st.error(classification)
