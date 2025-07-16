import streamlit as st
import boto3
import os
import io
import time
from dotenv import load_dotenv
from document_processor import DocumentProcessor
import json

load_dotenv()

# AWS config
aws_region = os.getenv("AWS_DEFAULT_REGION", "us-west-2").strip()
agent_id = os.getenv("BEDROCK_AGENT_ID", "").strip()
agent_alias_id = os.getenv("BEDROCK_AGENT_ALIAS_ID", "").strip()
step_function_arn = os.getenv("STEP_FUNCTION_ARN", "").strip()

# Initialize AWS clients
session = boto3.Session(region_name=aws_region)
sfn_client = session.client("stepfunctions")

# Initialize document processor
doc_processor = DocumentProcessor(aws_region, agent_id, agent_alias_id)

st.set_page_config(page_title="💬 Agent Query", layout="wide")
st.title("💬 Query the Real Estate AI Agent")
st.markdown("Use natural language to ask the agent about documents in the knowledge base.")

st.info("🔄 Knowledge Base syncs automatically when documents are uploaded in Home.py")
st.markdown("---")

# User query
query = st.text_input("Ask something about your documents:", placeholder="e.g., What properties were sold in June?")
if query:
    with st.spinner("🔍 Querying agent..."):
        try:
            response, citations = doc_processor.query_agent(query)
            st.success("✅ Agent response:")
            st.write(response)
            
            # Display citations if available
            if citations:
                st.markdown("---")
                st.subheader("📚 Sources & Citations")
                for i, citation in enumerate(citations, 1):
                    with st.expander(f"📄 Source {i} (Score: {citation.get('score', 0):.2f})"):
                        if citation.get('location'):
                            st.write(f"**Document:** {citation['location']}")
                        if citation.get('content'):
                            st.write(f"**Content:** {citation['content'][:500]}...")
        except Exception as e:
            st.error(f"Agent query failed: {e}")
