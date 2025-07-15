#!/usr/bin/env python3
"""
Test script for Bedrock classification
"""
import boto3
import os
import uuid
import time
from dotenv import load_dotenv
from io import BytesIO

# Load environment variables
load_dotenv()

# AWS Configuration
aws_region = os.getenv("AWS_DEFAULT_REGION", "us-west-2").strip()
agent_id = os.getenv("BEDROCK_AGENT_ID", "").strip()
agent_alias_id = os.getenv("BEDROCK_AGENT_ALIAS_ID", "").strip()

# Initialize AWS clients
session = boto3.Session(region_name=aws_region)
bedrock_runtime = session.client("bedrock-agent-runtime")

def classify_document(content, filename):
    """Test document classification with Bedrock"""
    
    # Create a mock file-like object
    file_obj = BytesIO(content.encode('utf-8'))
    
    # Strict prompt that forces only 3 categories or invalid
    prompt = f"""
You are a strict document classifier for real estate documents. You MUST classify this document into EXACTLY one of these 3 categories:

1. Settlement Documents
2. Income Verifications  
3. Purchase Agreements

IMPORTANT RULES:
- If the document has any of the categories listed inside, immediately classify it as one of the 3 categories
- Respond with ONLY the exact category name from the list above
- If the document does not clearly fit into any of these 3 categories, respond with: "INVALID_DOCUMENT"
- If the document is corrupted, unreadable, or not a real estate document, respond with: "INVALID_DOCUMENT"
- Do not provide explanations, descriptions, or any other text
- Do not create new categories

Document Content:
{content}
"""

    print(f"\n🔍 Testing classification for: {filename}")
    print(f"Content preview: {content[:100]}...")
    
    start_time = time.time()
    print("⏳ Calling Bedrock Agent...")
    
    try:
        response = bedrock_runtime.invoke_agent(
            agentId=agent_id,
            agentAliasId=agent_alias_id,
            sessionId=str(uuid.uuid4()),
            inputText=prompt
        )
        
        elapsed = time.time() - start_time
        print(f"⏱️ Bedrock response time: {elapsed:.2f} seconds")

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
            
            print(f"📝 Raw result from Bedrock: '{result}'")
            
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
                print(f"✅ Valid classification: {cleaned_result}")
                return cleaned_result
            
            # Check for partial matches (case insensitive)
            for category in valid_categories:
                if category.lower() in cleaned_result.lower():
                    print(f"✅ Partial match found: {category}")
                    return category
            
            # If no valid category found, mark as invalid
            print(f"❌ Invalid classification, returning: INVALID_DOCUMENT")
            return "INVALID_DOCUMENT"
        else:
            print("❌ No completion in response")
            return "INVALID_DOCUMENT"

    except Exception as e:
        print(f"❌ Error calling Bedrock Agent: {str(e)}")
        return "INVALID_DOCUMENT"

if __name__ == "__main__":
    # Test cases
    test_cases = [
        ("This is a settlement statement for a real estate transaction. It shows all the closing costs and final amounts paid by the buyer and received by the seller.", "settlement.pdf"),
        ("Income verification letter from employer confirming annual salary of $75,000 for mortgage application purposes.", "income.pdf"),
        ("Purchase agreement for residential property at 123 Main Street. Buyer agrees to purchase the property for $350,000.", "purchase.pdf"),
        ("This is just some random text that has nothing to do with real estate documents.", "random.txt")
    ]
    
    print("=" * 70)
    print("TESTING BEDROCK AGENT CLASSIFICATION")
    print("=" * 70)
    
    results = []
    
    for content, filename in test_cases:
        result = classify_document(content, filename)
        results.append((filename, result))
        print(f"🏁 Final classification: {result}")
        print("-" * 50)
    
    # Print summary
    print("\n📊 CLASSIFICATION SUMMARY:")
    print("=" * 70)
    for filename, result in results:
        valid = result != "INVALID_DOCUMENT"
        status = "✅ VALID" if valid else "❌ INVALID"
        print(f"{status} | {filename} | Classification: {result}")
