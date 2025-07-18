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
from document_processor import DocumentProcessor
import io
import asyncio
import concurrent.futures
from threading import Thread

# Load environment variables from .env if present
load_dotenv()

# Initialize session state for analytics
if 'total_cost' not in st.session_state:
    st.session_state.total_cost = 0.0
if 'documents_processed' not in st.session_state:
    st.session_state.documents_processed = 0
if 'successful_uploads' not in st.session_state:
    st.session_state.successful_uploads = 0
if 'dynamodb_records' not in st.session_state:
    st.session_state.dynamodb_records = 0
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

# AWS Configuration from env
aws_region = os.getenv("AWS_DEFAULT_REGION", "us-west-2").strip()
agent_id = os.getenv("BEDROCK_AGENT_ID", "").strip()
agent_alias_id = os.getenv("BEDROCK_AGENT_ALIAS_ID", "").strip()
bucket_name = os.getenv("S3_BUCKET_NAME", "").strip()

# Initialize AWS session using default credential chain
session = boto3.Session(region_name=aws_region)

# AWS clients
s3 = session.client("s3")
sfn_client = session.client("stepfunctions")
step_function_arn = os.getenv("STEP_FUNCTION_ARN", "").strip()

# Initialize document processor
doc_processor = DocumentProcessor(aws_region, agent_id, agent_alias_id)

# Check AWS credentials
def test_aws_connection():
    try:
        s3.list_buckets()
        return True, "AWS credentials are valid ✅"
    except Exception as e:
        return False, f"AWS credentials error: {str(e)}"

# Upload file to S3 asynchronously
def upload_to_s3_async(file_content, filename, classification):
    """Upload file content to S3 asynchronously"""
    def upload_task():
        try:
            folder = classification.replace(" ", "_").lower()
            s3_key = f"{folder}/{filename}"
            file_obj = io.BytesIO(file_content)
            s3.upload_fileobj(file_obj, bucket_name, s3_key)
            return s3_key
        except Exception as e:
            return None
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(upload_task)
        return future

# Check data quality and confidence
def check_data_confidence(extracted_data, classification):
    """Check confidence of extracted data"""
    confidence_score = 1.0
    required_fields = {
        "Income Verifications": ["employee_name", "employer_name", "annual_income"],
        "Settlement Documents": ["buyer_name", "seller_name", "property_address", "sale_price"],
        "Purchase Agreements": ["buyer_name", "seller_name", "property_address", "purchase_price"]
    }
    
    if classification in required_fields:
        missing_fields = []
        for field in required_fields[classification]:
            if not extracted_data.get(field) or str(extracted_data.get(field)).strip() == "":
                missing_fields.append(field)
                confidence_score -= 0.2
        
        if missing_fields:
            return confidence_score, missing_fields
    
    return confidence_score, []

# Calculate approximate cost
def calculate_cost(start_time, end_time):
    duration = end_time - start_time
    base_cost = 0.0008  # Base cost per request in USD
    time_cost = 0.00012 * duration  # Cost per second of processing
    return base_cost + time_cost

# Get S3 file counts
def get_s3_file_counts():
    """Get count of files in S3 bucket by folder"""
    try:
        response = s3.list_objects_v2(Bucket=bucket_name)
        if 'Contents' not in response:
            return {'total': 0, 'by_folder': {}}
        
        total_files = len(response['Contents'])
        folder_counts = {}
        
        for obj in response['Contents']:
            key = obj['Key']
            if '/' in key:
                folder = key.split('/')[0]
                folder_counts[folder] = folder_counts.get(folder, 0) + 1
            else:
                folder_counts['root'] = folder_counts.get('root', 0) + 1
        
        return {'total': total_files, 'by_folder': folder_counts}
    except Exception as e:
        return {'total': 0, 'by_folder': {}, 'error': str(e)}

# Update analytics sidebar
def update_analytics_sidebar():
    with st.session_state.sidebar_container.container():
        st.header("📊 Real-Time Analytics")
        
        # S3 Storage Statistics (Top Section)
        st.subheader("☁️ S3 Storage")
        s3_stats = get_s3_file_counts()
        
        if 'error' in s3_stats:
            st.error(f"S3 Error: {s3_stats['error']}")
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Files in S3", s3_stats['total'])
            with col2:
                if s3_stats['by_folder']:
                    most_files_folder = max(s3_stats['by_folder'], key=s3_stats['by_folder'].get)
                    st.metric(f"Largest Folder", f"{most_files_folder} ({s3_stats['by_folder'][most_files_folder]})")
            
            # Show folder breakdown
            if s3_stats['by_folder']:
                st.write("**Files by Folder:**")
                for folder, count in s3_stats['by_folder'].items():
                    st.write(f"• {folder}: {count} files")
        
        st.markdown("---")
        
        # Document processing metrics
        st.subheader("📄 Document Processing")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Documents Processed", st.session_state.documents_processed)
            st.metric("S3 Uploads", st.session_state.successful_uploads)
        with col2:
            st.metric("DynamoDB Records", st.session_state.dynamodb_records)
        
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
        
        # DynamoDB Status
        st.subheader("🗄️ DynamoDB Status")
        try:
            db_status = doc_processor.get_dynamodb_status()
            for table_name, info in db_status.items():
                if 'error' not in info:
                    st.success(f"{table_name}: {info.get('status', 'Unknown')}")
                else:
                    st.error(f"{table_name}: {info['error']}")
        except Exception as e:
            st.error(f"DynamoDB connection error: {str(e)}")
        
        # AWS Information
        st.subheader("☁️ AWS Information")
        st.info(f"Region: {aws_region}")
        st.info(f"S3 Bucket: {bucket_name}")
        st.info(f"Agent ID: {agent_id}")

# Enhanced document processing with DynamoDB storage
def process_document_enhanced(file_content, filename):
    """Process document with classification, extraction, and DynamoDB storage"""
    process_start_time = time.time()
    
    try:
        # Create a file-like object for the document processor
        file_obj = io.BytesIO(file_content)
        
        # First classify and extract data (now with proper PDF handling)
        with st.spinner(f'🤖 Analyzing {filename} with Bedrock Agent...'):
            classification, extracted_data = doc_processor.classify_and_extract(
                file_obj, 
                s3_path="", 
                filename=filename
            )
        
        # Check if there was an error in processing
        if 'error' in extracted_data:
            st.warning(f"⚠️ Processing warning for {filename}: {extracted_data['error']}")
        
        # Check data confidence
        confidence_score, missing_fields = check_data_confidence(extracted_data, classification)
        
        if confidence_score < 0.6 or missing_fields:
            st.error(f"⚠️ Low confidence extraction for {filename}")
            st.error(f"Missing fields: {', '.join(missing_fields)}")
            st.warning("📝 Manual extraction required - Document NOT uploaded to S3 or stored in DynamoDB")
            st.info("Please review and manually process this document")
            
            # Return early without uploading or storing
            process_end_time = time.time()
            process_duration = process_end_time - process_start_time
            
            # Update analytics for failed processing
            st.session_state.processing_times.append(process_duration)
            st.session_state.total_cost += calculate_cost(process_start_time, process_end_time)
            st.session_state.documents_processed += 1
            # Don't increment successful_uploads or dynamodb_records
            
            return classification, extracted_data, None, None, process_duration
        
        # Only proceed with upload and storage if confidence is high
        # Upload to S3 asynchronously (immediate)
        upload_future = upload_to_s3_async(file_content, filename, classification)
        s3_path = upload_future.result()  # Wait for upload completion
        
        if not s3_path:
            st.error(f"Failed to upload {filename} to S3")
            return None, None, None, None, 0
        
        # Trigger Knowledge Base sync after successful upload
        if step_function_arn:
            try:
                sfn_client.start_execution(
                    stateMachineArn=step_function_arn,
                    name=f"auto-sync-{int(time.time())}-{uuid.uuid4().hex[:8]}",
                    input=json.dumps({})
                )
                st.info("🔄 Knowledge Base sync started automatically")
            except Exception as e:
                st.warning(f"⚠️ Could not auto-sync Knowledge Base: {str(e)}")
        
        # Update extracted data with S3 path and confidence
        extracted_data['document_s3_path'] = f"s3://{bucket_name}/{s3_path}"
        extracted_data['confidence_score'] = confidence_score
        extracted_data['missing_fields'] = missing_fields
        
        # Store extracted data in DynamoDB
        with st.spinner('💾 Storing structured data in DynamoDB...'):
            record_id = doc_processor.store_extracted_data(classification, extracted_data)
        
        # Calculate processing time and cost
        process_end_time = time.time()
        process_duration = process_end_time - process_start_time
        
        # Update analytics (only for successful processing)
        st.session_state.processing_times.append(process_duration)
        st.session_state.total_cost += calculate_cost(process_start_time, process_end_time)
        st.session_state.documents_processed += 1
        st.session_state.successful_uploads += 1
        if record_id:
            st.session_state.dynamodb_records += 1
        st.session_state.category_counts[classification] += 1
        
        # Update sidebar analytics after each document
        st.session_state.sidebar_container.empty()
        update_analytics_sidebar()
        
        return classification, extracted_data, s3_path, record_id, process_duration
        
    except Exception as e:
        st.error(f"Error processing document {filename}: {str(e)}")
        return None, None, None, None, 0

# Streamlit UI
st.set_page_config(page_title="Enhanced Real Estate Document Processor", layout="wide")
st.title("🏡 Enhanced Real Estate Document Processor")
st.subheader("AWS Bedrock + S3 + DynamoDB Integration with PDF Support")

# Navigation info
st.info("💡 After uploading documents, go to **QueryAgent** in the sidebar to query your knowledge base!")

# Initialize sidebar container
if 'sidebar_container' not in st.session_state:
    st.session_state.sidebar_container = st.sidebar.empty()

# Initialize the sidebar
update_analytics_sidebar()

# Main content area
with st.container():
    # Credential check
    is_connected, connection_msg = test_aws_connection()
    if is_connected:
        st.success(connection_msg)
    else:
        st.error(connection_msg)
        st.stop()

    # File uploader
    uploaded_files = st.file_uploader(
        "📁 Upload multiple real estate documents",
        type=["pdf", "png", "jpg", "jpeg", "docx", "txt"],
        accept_multiple_files=True,
        help="Supported formats: PDF, Images (PNG, JPG, JPEG), Word documents, Text files"
    )

    # Process uploaded files
    if uploaded_files:
        st.info("🔍 Processing documents with enhanced extraction and PDF support...")
        
        # Create tabs for different views
        tab1, tab2, tab3 = st.tabs(["📄 Processing Results", "🗄️ Extracted Data", "📊 Summary"])
        
        processing_results = []
        
        # Process each file
        for i, file in enumerate(uploaded_files):
            # Read file content once
            file_content = file.read()
            
            with tab1:
                st.markdown(f"#### 📄 Processing: {file.name}")
                
                # Show file info
                file_size = len(file_content)
                st.write(f"📊 File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
                st.write(f"📄 File type: {file.name.split('.')[-1].upper()}")
                
                result = process_document_enhanced(file_content, file.name)
                if result[0]:  # If processing was successful
                    classification, extracted_data, s3_path, record_id, duration = result
                    processing_results.append({
                        'filename': file.name,
                        'classification': classification,
                        'extracted_data': extracted_data,
                        's3_path': s3_path,
                        'record_id': record_id,
                        'duration': duration
                    })
                    
                    st.success(f"✅ Classified as: `{classification}`")
                    
                    # Only show S3 and DynamoDB messages if actually uploaded/stored
                    if s3_path:
                        st.write(f"☁️ Uploaded to S3: `s3://{bucket_name}/{s3_path}`")
                    if record_id:
                        st.write(f"🗼️ Stored in DynamoDB with ID: `{record_id}`")
                    
                    st.write(f"⏱️ Processing time: {duration:.2f} seconds")
                    
                    # Show extracted data preview
                    with st.expander("🔍 View Extracted Data"):
                        st.json(extracted_data)
                else:
                    st.error(f"❌ Failed to process {file.name}")
                
                st.markdown("---")
        
        # Show extracted data in structured format
        with tab2:
            if processing_results:
                st.subheader("🗄️ Structured Data Extracted")
                
                for result in processing_results:
                    st.markdown(f"### {result['filename']}")
                    st.write(f"**Classification:** {result['classification']}")
                    
                    # Display key extracted fields based on document type
                    data = result['extracted_data']
                    
                    if "Income Verification" in result['classification']:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Employee:** {data.get('employee_name', 'N/A')}")
                            st.write(f"**Employer:** {data.get('employer_name', 'N/A')}")
                            st.write(f"**Job Title:** {data.get('job_title', 'N/A')}")
                        with col2:
                            annual_income = data.get('annual_income', 0)
                            monthly_income = data.get('monthly_income', 0)
                            
                            # Handle None values and convert to float
                            if annual_income is None:
                                annual_income = 0
                            elif isinstance(annual_income, str):
                                try:
                                    annual_income = float(annual_income)
                                except:
                                    annual_income = 0
                            
                            if monthly_income is None:
                                monthly_income = 0
                            elif isinstance(monthly_income, str):
                                try:
                                    monthly_income = float(monthly_income)
                                except:
                                    monthly_income = 0
                            
                            st.write(f"**Annual Income:** ${annual_income:,.0f}")
                            st.write(f"**Monthly Income:** ${monthly_income:,.0f}")
                            st.write(f"**Employment Status:** {data.get('employment_status', 'N/A')}")
                    
                    elif "Settlement" in result['classification']:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Buyer:** {data.get('buyer_name', 'N/A')}")
                            st.write(f"**Seller:** {data.get('seller_name', 'N/A')}")
                            st.write(f"**Property:** {data.get('property_address', 'N/A')}")
                        with col2:
                            sale_price = data.get('sale_price', 0)
                            loan_amount = data.get('loan_amount', 0)
                            
                            # Handle None values and convert to float
                            if sale_price is None:
                                sale_price = 0
                            elif isinstance(sale_price, str):
                                try:
                                    sale_price = float(sale_price)
                                except:
                                    sale_price = 0
                            
                            if loan_amount is None:
                                loan_amount = 0
                            elif isinstance(loan_amount, str):
                                try:
                                    loan_amount = float(loan_amount)
                                except:
                                    loan_amount = 0
                            
                            st.write(f"**Sale Price:** ${sale_price:,.0f}")
                            st.write(f"**Loan Amount:** ${loan_amount:,.0f}")
                            st.write(f"**Settlement Date:** {data.get('settlement_date', 'N/A')}")
                    
                    elif "Purchase Agreement" in result['classification']:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Buyer:** {data.get('buyer_name', 'N/A')}")
                            st.write(f"**Seller:** {data.get('seller_name', 'N/A')}")
                            st.write(f"**Property:** {data.get('property_address', 'N/A')}")
                        with col2:
                            purchase_price = data.get('purchase_price', 0)
                            down_payment = data.get('down_payment', 0)
                            
                            # Handle None values and convert to float
                            if purchase_price is None:
                                purchase_price = 0
                            elif isinstance(purchase_price, str):
                                try:
                                    purchase_price = float(purchase_price)
                                except:
                                    purchase_price = 0
                            
                            if down_payment is None:
                                down_payment = 0
                            elif isinstance(down_payment, str):
                                try:
                                    down_payment = float(down_payment)
                                except:
                                    down_payment = 0
                            
                            st.write(f"**Purchase Price:** ${purchase_price:,.0f}")
                            st.write(f"**Down Payment:** ${down_payment:,.0f}")
                            st.write(f"**Closing Date:** {data.get('closing_date', 'N/A')}")
                    
                    st.markdown("---")
        
        # Show summary
        with tab3:
            if processing_results:
                st.subheader("📊 Processing Summary")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Documents Processed", len(processing_results))
                with col2:
                    st.metric("S3 Uploads", len([r for r in processing_results if r['s3_path']]))
                with col3:
                    st.metric("DynamoDB Records", len([r for r in processing_results if r['record_id']]))
                with col4:
                    total_time = sum([r['duration'] for r in processing_results])
                    st.metric("Total Time", f"{total_time:.2f}s")
                
                # Show breakdown by document type
                st.subheader("📋 Document Type Breakdown")
                type_counts = {}
                for result in processing_results:
                    doc_type = result['classification']
                    type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
                
                for doc_type, count in type_counts.items():
                    st.write(f"• **{doc_type}:** {count} document(s)")

    # Navigation to QueryAgent
    st.markdown("---")
    st.subheader("🔍 Next Steps")
    st.write("After processing documents, use the **QueryAgent** page (in sidebar) to:")
    st.write("• Query your uploaded documents")
    st.write("• Ask questions about your real estate data")
    st.write("• Knowledge Base syncs automatically after uploads")
    
    # Clear button to reset session
    if st.button("🔄 Clear Session Data"):
        for key in ['total_cost', 'documents_processed', 'successful_uploads', 
                   'dynamodb_records', 'processing_times', 'category_counts']:
            if key in st.session_state:
                if key == 'category_counts':
                    st.session_state[key] = {
                        "Settlement Documents": 0,
                        "Income Verifications": 0,
                        "Purchase Agreements": 0
                    }
                elif key == 'processing_times':
                    st.session_state[key] = []
                else:
                    st.session_state[key] = 0
        st.session_state.start_time = time.time()
        st.success("Session data cleared!")
        st.rerun()
