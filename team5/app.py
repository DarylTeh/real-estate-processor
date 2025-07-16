import streamlit as st
import boto3
import os
import json
import time
import datetime
import pandas as pd
from dotenv import load_dotenv
from pathlib import Path
import uuid

# Load environment variables from .env if present
load_dotenv()

# Initialize session state for analytics
if 'total_cost' not in st.session_state:
    st.session_state.total_cost = 0.0
if 'documents_processed' not in st.session_state:
    st.session_state.documents_processed = 0
if 'successful_uploads' not in st.session_state:
    st.session_state.successful_uploads = 0
if 'processing_times' not in st.session_state:
    st.session_state.processing_times = []
if 'category_counts' not in st.session_state:
    st.session_state.category_counts = {
        "Settlement Documents": 0,
        "Income Verifications": 0,
        "Purchase Agreements": 0
    }
if 'start_time' not in st.session_state:
    st.session_state.start_time = time.time()
if 'last_sidebar_update' not in st.session_state:
    st.session_state.last_sidebar_update = 0

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
    # Use original filename instead of UUID
    filename = f"{folder}/{file.name}"
    s3.upload_fileobj(file, bucket_name, filename)
    return filename


# 💰 Calculate approximate cost (this is an estimate)
def calculate_cost(start_time, end_time):
    # Duration in seconds
    duration = end_time - start_time
    
    # Approximate cost calculation based on Bedrock pricing
    # These are placeholder values - adjust based on actual pricing
    base_cost = 0.0008  # Base cost per request in USD
    time_cost = 0.00012 * duration  # Cost per second of processing
    
    return base_cost + time_cost


# 📊 Update analytics sidebar
def update_analytics_sidebar():
    # Use a single sidebar container to avoid duplication
    sidebar_container = st.sidebar.container()
    
    with sidebar_container:
        st.header("📊 Real-Time Analytics")
        
        # Session duration - recalculated each time
        current_time = time.time()
        session_duration = current_time - st.session_state.start_time
        minutes, seconds = divmod(int(session_duration), 60)
        hours, minutes = divmod(minutes, 60)
        
        st.subheader("⏱️ Session Information")
        duration_placeholder = st.empty()
        duration_placeholder.info(f"Session Duration: {hours:02d}:{minutes:02d}:{seconds:02d}")
        
        # Document processing metrics
        st.subheader("📄 Document Processing")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Documents Processed", st.session_state.documents_processed)
        with col2:
            st.metric("Successfully Uploaded", st.session_state.successful_uploads)
        
        # Cost information
        st.subheader("💰 Cost Information")
        st.metric("Estimated Cost", f"${st.session_state.total_cost:.4f}")
        
        # Average processing time
        if st.session_state.processing_times:
            avg_time = sum(st.session_state.processing_times) / len(st.session_state.processing_times)
            st.metric("Avg. Processing Time", f"{avg_time:.2f} sec")
        
        # Category distribution
        st.subheader("📊 Document Categories")
        categories = list(st.session_state.category_counts.keys())
        counts = list(st.session_state.category_counts.values())
        
        if sum(counts) > 0:
            chart_data = pd.DataFrame({
                'Category': categories,
                'Count': counts
            })
            st.bar_chart(chart_data.set_index('Category'))
        
        # AWS Information
        st.subheader("☁️ AWS Information")
        st.info(f"Region: {aws_region}")
        st.info(f"S3 Bucket: {bucket_name}")
        st.info(f"Agent ID: {agent_id}")
        
    # Return the duration placeholder for updating
    return duration_placeholder


# 🧠 Classify document using Bedrock Agent with extremely lenient validation
def classify_document(file):
    file_content = file.read()
    file.seek(0)

    prompt = f"""
You are an EXTREMELY LENIENT document classifier for real estate documents. Your goal is to classify EVERY document into one of these 3 categories, even with minimal evidence:

1. Settlement Documents
2. Income Verifications  
3. Purchase Agreements

CRITICAL INSTRUCTIONS:
- Your PRIMARY goal is to classify EVERY document into one of the three categories above - avoid "INVALID_DOCUMENT" at all costs
- Use the SLIGHTEST hint or keyword to make a classification decision
- If you see ANY mention of money, payments, transactions, or financial details, classify as "Settlement Documents"
- If you see ANY mention of income, salary, employment, job, earnings, or financial status, classify as "Income Verifications"
- If you see ANY mention of property, real estate, house, agreement, contract, terms, or conditions, classify as "Purchase Agreements"
- When in doubt between categories, use this priority: 1) Income Verifications, 2) Settlement Documents, 3) Purchase Agreements
- If truly uncertain, default to "Purchase Agreements" rather than returning "INVALID_DOCUMENT"
- ONLY use "INVALID_DOCUMENT" if the content is COMPLETELY unrelated to anything that could possibly be a real estate document
- Respond with ONLY the exact category name from the list above
- Do not provide explanations, descriptions, or any other text

Document Content:
{file_content[:3000].decode(errors='ignore')}
"""

    try:
        # Record start time for processing
        process_start_time = time.time()
        
        # Add progress indicator
        with st.spinner(f'🤖 Analyzing {file.name} with Bedrock Agent...'):
            response = bedrock_runtime.invoke_agent(
                agentId=agent_id,
                agentAliasId=agent_alias_id,
                sessionId=str(uuid.uuid4()),
                inputText=prompt
            )
        
        # Record end time and calculate metrics
        process_end_time = time.time()
        process_duration = process_end_time - process_start_time
        
        # Update analytics
        st.session_state.processing_times.append(process_duration)
        st.session_state.total_cost += calculate_cost(process_start_time, process_end_time)
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
            
            # Super lenient validation - try everything possible to classify
            valid_categories = [
                "Settlement Documents",
                "Income Verifications", 
                "Purchase Agreements"
            ]
            
            # Clean up the result
            cleaned_result = result.strip().lower()
            
            # Check for exact match first (case insensitive)
            for category in valid_categories:
                if category.lower() == cleaned_result:
                    # Update category count
                    st.session_state.category_counts[category] += 1
                    return category
            
            # Check for partial matches (case insensitive)
            for category in valid_categories:
                if category.lower() in cleaned_result:
                    # Update category count
                    st.session_state.category_counts[category] += 1
                    return category
            
            # Check for keyword matches
            if any(keyword in cleaned_result for keyword in ["settlement", "closing", "hud", "escrow", "title", "transaction", "payment", "money", "financial", "cash", "funds"]):
                st.session_state.category_counts["Settlement Documents"] += 1
                return "Settlement Documents"
            
            if any(keyword in cleaned_result for keyword in ["income", "salary", "employment", "job", "earnings", "verification", "pay", "tax", "w-2", "wage"]):
                st.session_state.category_counts["Income Verifications"] += 1
                return "Income Verifications"
            
            if any(keyword in cleaned_result for keyword in ["purchase", "agreement", "contract", "sale", "offer", "buyer", "seller", "property", "house", "home", "real estate", "terms"]):
                st.session_state.category_counts["Purchase Agreements"] += 1
                return "Purchase Agreements"
            
            # Last resort - default to Purchase Agreements rather than invalid
            st.session_state.category_counts["Purchase Agreements"] += 1
            return "Purchase Agreements"
        else:
            # Default to Purchase Agreements if no completion
            st.session_state.category_counts["Purchase Agreements"] += 1
            return "Purchase Agreements"

    except Exception as e:
        st.error(f"Error calling Bedrock Agent: {str(e)}")
        # Default to Purchase Agreements even on error
        st.session_state.category_counts["Purchase Agreements"] += 1
        return "Purchase Agreements"


# 🌐 Streamlit UI
st.set_page_config(page_title="Real Estate Document Classifier", layout="wide")
st.title("🏡 Real Estate Document Classifier (AWS Bedrock + S3)")

# Initialize the sidebar once
duration_placeholder = update_analytics_sidebar()

# Main content area
main_content = st.container()

with main_content:
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

    # Process uploaded files
    if uploaded_files and 'processing_complete' not in st.session_state:
        st.session_state.processing_complete = False
        st.session_state.current_files = uploaded_files
        st.info("🔍 Classifying documents...")
        
        # Track results
        successful_uploads = 0
        
        for file in uploaded_files:
            st.markdown(f"#### 📄 {file.name}")
            classification = classify_document(file)

            # With our extremely lenient approach, we should almost always get a valid category
            valid_categories = ["Settlement Documents", "Income Verifications", "Purchase Agreements"]
            
            # All documents should be classified now
            st.success(f"✅ Classified as: `{classification}`")
            file.seek(0)  # Reset for upload
            s3_path = upload_to_s3(file, classification)
            st.write(f"☁️ Uploaded to S3: `s3://{bucket_name}/{s3_path}`")
            successful_uploads += 1
            st.session_state.successful_uploads += 1
            
            # Only update the timer, not the whole sidebar
            current_time = time.time()
            session_duration = current_time - st.session_state.start_time
            minutes, seconds = divmod(int(session_duration), 60)
            hours, minutes = divmod(minutes, 60)
            duration_placeholder.info(f"Session Duration: {hours:02d}:{minutes:02d}:{seconds:02d}")
        
        # Show summary
        st.markdown("---")
        st.markdown("### 📊 Upload Summary")
        st.metric("✅ Successfully Uploaded", successful_uploads)
        
        # Show time and cost summary
        if st.session_state.processing_times:
            total_time = sum(st.session_state.processing_times)
            avg_time = total_time / len(st.session_state.processing_times)
            st.write(f"⏱️ Total processing time: {total_time:.2f} seconds (avg: {avg_time:.2f} sec per document)")
            st.write(f"💰 Estimated cost: ${st.session_state.total_cost:.4f}")
        
        st.session_state.processing_complete = True
        
        # Update the sidebar once after all processing is complete
        # duration_placeholder = update_analytics_sidebar()
    
    # Display previous results if processing is complete
    elif 'processing_complete' in st.session_state and st.session_state.processing_complete:
        if 'current_files' in st.session_state and st.session_state.current_files:
            st.info("✅ Classification complete")
            
            # Show summary
            st.markdown("---")
            st.markdown("### 📊 Upload Summary")
            st.metric("✅ Successfully Uploaded", st.session_state.successful_uploads)
            
            # Show time and cost summary
            if st.session_state.processing_times:
                total_time = sum(st.session_state.processing_times)
                avg_time = total_time / len(st.session_state.processing_times)
                st.write(f"⏱️ Total processing time: {total_time:.2f} seconds (avg: {avg_time:.2f} sec per document)")
                st.write(f"💰 Estimated cost: ${st.session_state.total_cost:.4f}")
            
            # Reset if new files are uploaded
            if uploaded_files != st.session_state.current_files:
                st.session_state.processing_complete = False
                st.rerun()
    
    # Update just the timer without recreating the whole sidebar
    current_time = time.time()
    session_duration = current_time - st.session_state.start_time
    minutes, seconds = divmod(int(session_duration), 60)
    hours, minutes = divmod(minutes, 60)
    duration_placeholder.info(f"Session Duration: {hours:02d}:{minutes:02d}:{seconds:02d}")
    
    # Only update the full sidebar once per second
    if current_time - st.session_state.last_sidebar_update >= 1.0:
        # duration_placeholder = update_analytics_sidebar()
        st.session_state.last_sidebar_update = current_time
    
    # Auto-rerun the app every second to update the timer
    time.sleep(1)
    st.rerun()
