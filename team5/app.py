import streamlit as st
import boto3
import os
import json
import time
from dotenv import load_dotenv
from pathlib import Path
import uuid

# Load environment variables from .env if present (for local development)
load_dotenv()

# AWS Configuration - try to get from Streamlit secrets first, then fall back to env vars
aws_region = st.secrets.get("AWS_DEFAULT_REGION", os.getenv("AWS_DEFAULT_REGION", "us-west-2")).strip()
agent_id = st.secrets.get("BEDROCK_AGENT_ID", os.getenv("BEDROCK_AGENT_ID", "")).strip()
agent_alias_id = st.secrets.get("BEDROCK_AGENT_ALIAS_ID", os.getenv("BEDROCK_AGENT_ALIAS_ID", "")).strip()
knowledge_base_id = st.secrets.get("BEDROCK_KNOWLEDGE_BASE_ID", os.getenv("BEDROCK_KNOWLEDGE_BASE_ID", "")).strip()
bucket_name = st.secrets.get("S3_BUCKET_NAME", os.getenv("S3_BUCKET_NAME", "")).strip()

# Check for AWS credentials in Streamlit secrets
aws_access_key = st.secrets.get("aws_credentials", {}).get("AWS_ACCESS_KEY_ID", None)
aws_secret_key = st.secrets.get("aws_credentials", {}).get("AWS_SECRET_ACCESS_KEY", None)

# Initialize AWS session using credentials from secrets if available, otherwise use default credential chain
if aws_access_key and aws_secret_key:
    session = boto3.Session(
        region_name=aws_region,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key
    )
else:
    session = boto3.Session(region_name=aws_region)

# AWS clients
s3 = session.client("s3")
bedrock_runtime = session.client("bedrock-agent-runtime")
bedrock_agent = session.client("bedrock-agent")

# Initialize session state for analytics
if 'total_cost' not in st.session_state:
    st.session_state.total_cost = 0.0
if 'documents_processed' not in st.session_state:
    st.session_state.documents_processed = 0
if 'successful_uploads' not in st.session_state:
    st.session_state.successful_uploads = 0
if 'failed_uploads' not in st.session_state:
    st.session_state.failed_uploads = 0
if 'agent_info' not in st.session_state:
    st.session_state.agent_info = None
if 'kb_info' not in st.session_state:
    st.session_state.kb_info = None


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


# 🧠 Get agent information
def get_agent_info():
    try:
        response = bedrock_agent.get_agent(
            agentId=agent_id
        )
        return response
    except Exception as e:
        st.error(f"Error fetching agent info: {str(e)}")
        return None


# 📚 Get knowledge base information
def get_knowledge_base_info():
    try:
        response = bedrock_agent.get_knowledge_base(
            knowledgeBaseId=knowledge_base_id
        )
        return response
    except Exception as e:
        st.error(f"Error fetching knowledge base info: {str(e)}")
        return None


# 💰 Calculate approximate cost (this is an estimate)
def calculate_cost(start_time, end_time):
    # Duration in seconds
    duration = end_time - start_time
    
    # Approximate cost calculation based on Bedrock pricing
    # These are placeholder values - adjust based on actual pricing
    base_cost = 0.0008  # Base cost per request in USD
    time_cost = 0.00012 * duration  # Cost per second of processing
    
    return base_cost + time_cost


# 🧠 Classify document using Bedrock Agent with strict validation
def classify_document(file):
    file_content = file.read()
    file.seek(0)

    prompt = f"""
You are a lenient document classifier for real estate documents. You MUST classify this document into EXACTLY one of these 3 categories:

1. Settlement Documents
2. Income Verifications  
3. Purchase Agreements

IMPORTANT RULES:
- Be flexible in your classification approach - these are real documents that need proper categorization
- If the document mentions income, salary, employment verification, pay stubs, or tax returns, classify it as "Income Verifications"
- If the document mentions settlement, closing, HUD-1, escrow, title transfer, or property transaction details, classify it as "Settlement Documents"
- If the document mentions purchase, sale, offer, buyer, seller, or property acquisition terms, classify it as "Purchase Agreements"
- Look for the general purpose and content of the document rather than exact phrases
- Respond with ONLY the exact category name from the list above
- Only use "INVALID_DOCUMENT" if the content is completely unrelated to real estate transactions
- Do not provide explanations, descriptions, or any other text

Document Content:
{file_content[:3000].decode(errors='ignore')}
"""

    try:
        # Add progress indicator
        with st.spinner(f'🤖 Analyzing {file.name} with Bedrock Agent...'):
            # Record start time for cost calculation
            start_time = time.time()
            
            response = bedrock_runtime.invoke_agent(
                agentId=agent_id,
                agentAliasId=agent_alias_id,
                sessionId=str(uuid.uuid4()),
                inputText=prompt
            )
            
            # Record end time for cost calculation
            end_time = time.time()
            
            # Calculate and add to total cost
            request_cost = calculate_cost(start_time, end_time)
            st.session_state.total_cost += request_cost
            st.session_state.documents_processed += 1

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

# Fetch agent and KB info if not already fetched
if st.session_state.agent_info is None:
    st.session_state.agent_info = get_agent_info()
if st.session_state.kb_info is None:
    st.session_state.kb_info = get_knowledge_base_info()

# Create tabs for main app and analytics
tab1, tab2 = st.tabs(["📄 Document Processor", "📊 Analytics"])

with tab1:
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
                st.session_state.successful_uploads += 1
            elif classification == "INVALID_DOCUMENT":
                st.error(f"❌ Document rejected: This file does not match any of the required real estate document categories (Settlement Documents, Income Verifications, Purchase Agreements)")
                st.warning("⚠️ File was not uploaded to S3")
                failed_uploads += 1
                st.session_state.failed_uploads += 1
            else:
                # Fallback for any other response
                st.error(f"❌ Classification failed: Unable to properly classify this document")
                st.warning("⚠️ File was not uploaded to S3")
                failed_uploads += 1
                st.session_state.failed_uploads += 1
        
        # Show summary
        st.markdown("---")
        st.markdown("### 📊 Upload Summary")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("✅ Successfully Uploaded", successful_uploads)
        with col2:
            st.metric("❌ Rejected Files", failed_uploads)

with tab2:
    st.header("📈 System Analytics")
    
    # Create three columns for metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("💰 Estimated Cost", f"${st.session_state.total_cost:.4f}")
    with col2:
        st.metric("📄 Documents Processed", st.session_state.documents_processed)
    with col3:
        success_rate = 0 if st.session_state.documents_processed == 0 else (st.session_state.successful_uploads / st.session_state.documents_processed) * 100
        st.metric("✅ Success Rate", f"{success_rate:.1f}%")
    
    # AWS Configuration Information
    st.subheader("🔧 AWS Configuration")
    
    config_col1, config_col2 = st.columns(2)
    
    with config_col1:
        st.markdown("**AWS Region:** " + aws_region)
        st.markdown("**S3 Bucket:** " + bucket_name)
    
    with config_col2:
        st.markdown("**Agent ID:** " + agent_id)
        st.markdown("**Agent Alias ID:** " + agent_alias_id)
        if knowledge_base_id:
            st.markdown("**Knowledge Base ID:** " + knowledge_base_id)
    
    # Agent Information
    if st.session_state.agent_info:
        st.subheader("🤖 Agent Information")
        agent_info = st.session_state.agent_info
        
        agent_col1, agent_col2 = st.columns(2)
        
        with agent_col1:
            st.markdown(f"**Agent Name:** {agent_info.get('name', 'N/A')}")
            st.markdown(f"**Created At:** {agent_info.get('createdAt', 'N/A').strftime('%Y-%m-%d %H:%M:%S') if hasattr(agent_info.get('createdAt', 'N/A'), 'strftime') else 'N/A'}")
            st.markdown(f"**Foundation Model:** {agent_info.get('foundationModel', 'N/A')}")
        
        with agent_col2:
            st.markdown(f"**Description:** {agent_info.get('description', 'N/A')}")
            st.markdown(f"**Status:** {agent_info.get('agentStatus', 'N/A')}")
    
    # Knowledge Base Information
    if st.session_state.kb_info:
        st.subheader("📚 Knowledge Base Information")
        kb_info = st.session_state.kb_info
        
        kb_col1, kb_col2 = st.columns(2)
        
        with kb_col1:
            st.markdown(f"**KB Name:** {kb_info.get('name', 'N/A')}")
            st.markdown(f"**Created At:** {kb_info.get('createdAt', 'N/A').strftime('%Y-%m-%d %H:%M:%S') if hasattr(kb_info.get('createdAt', 'N/A'), 'strftime') else 'N/A'}")
        
        with kb_col2:
            st.markdown(f"**Description:** {kb_info.get('description', 'N/A')}")
            st.markdown(f"**Status:** {kb_info.get('status', 'N/A')}")
    
    # Usage Statistics
    st.subheader("📊 Usage Statistics")
    
    # Create a simple bar chart for document categories
    if st.session_state.documents_processed > 0:
        st.bar_chart({
            "Successful": st.session_state.successful_uploads,
            "Failed": st.session_state.failed_uploads
        })
