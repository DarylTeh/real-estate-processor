#!/usr/bin/env python3
"""
Test direct Bedrock classification
"""
import boto3
import os
import uuid
from dotenv import load_dotenv
from io import BytesIO

load_dotenv()

# AWS Configuration
aws_region = os.getenv("AWS_DEFAULT_REGION", "us-west-2").strip()
agent_id = os.getenv("BEDROCK_AGENT_ID", "").strip()
agent_alias_id = os.getenv("BEDROCK_AGENT_ALIAS_ID", "").strip()

session = boto3.Session(region_name=aws_region)
bedrock_runtime = session.client("bedrock-agent-runtime")

def test_classify_document(content_text, filename):
    """Test document classification"""
    
    prompt = f"""
You are a strict document classifier for real estate documents. You MUST classify this document into EXACTLY one of these 3 categories:

1. Settlement Documents
2. Income Verifications  
3. Purchase Agreements

IMPORTANT RULES:
- Respond with ONLY the exact category name from the list above
- If the document does not clearly fit into any of these 3 categories, respond with: "INVALID_DOCUMENT"
- If the document is corrupted, unreadable, or not a real estate document, respond with: "INVALID_DOCUMENT"
- Do not provide explanations, descriptions, or any other text
- Do not create new categories

Document Content:
{content_text}
"""

    try:
        print(f"🤖 Testing classification for: {filename}")
        print(f"Content: {content_text[:100]}...")
        
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
            
            print(f"Raw result: '{result}'")
            
            # Strict validation
            valid_categories = [
                "Settlement Documents",
                "Income Verifications", 
                "Purchase Agreements"
            ]
            
            cleaned_result = result.strip()
            
            if cleaned_result in valid_categories:
                print(f"✅ Valid classification: {cleaned_result}")
                return cleaned_result
            
            for category in valid_categories:
                if category.lower() in cleaned_result.lower():
                    print(f"✅ Partial match found: {category}")
                    return category
            
            print(f"❌ Invalid classification, returning: INVALID_DOCUMENT")
            return "INVALID_DOCUMENT"
        else:
            print("❌ No completion in response")
            return "INVALID_DOCUMENT"

    except Exception as e:
        print(f"❌ Error: {e}")
        return "INVALID_DOCUMENT"

if __name__ == "__main__":
    # Test cases
    test_cases = [
        ("This is a settlement statement showing the final costs and payments for a real estate transaction closing.", "settlement.pdf"),
        ("Employment verification letter confirming salary and employment status for mortgage application.", "income.pdf"),
        ("Purchase agreement contract for buying a residential property at 123 Main Street.", "purchase.pdf"),
        ("This is just some random text that has nothing to do with real estate.", "random.txt")
    ]
    
    print("Testing Direct Bedrock Classification:")
    print("=" * 60)
    
    for content, filename in test_cases:
        result = test_classify_document(content, filename)
        print(f"Final result: {result}")
        print("-" * 40)
