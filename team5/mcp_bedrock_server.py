#!/usr/bin/env python3
"""
MCP Server for AWS Bedrock Agent integration
"""
import asyncio
import json
import os
import uuid
import boto3
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# AWS Configuration
aws_region = os.getenv("AWS_DEFAULT_REGION", "us-west-2").strip()
agent_id = os.getenv("BEDROCK_AGENT_ID", "").strip()
agent_alias_id = os.getenv("BEDROCK_AGENT_ALIAS_ID", "").strip()

# Initialize AWS clients
session = boto3.Session(region_name=aws_region)
bedrock_runtime = session.client("bedrock-agent-runtime")

# Create MCP server
server = Server("bedrock-agent")

@server.list_tools()
async def list_tools():
    """List available tools"""
    return [
        Tool(
            name="classify_document",
            description="Classify a document using AWS Bedrock Agent",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Document content to classify"
                    },
                    "filename": {
                        "type": "string", 
                        "description": "Name of the file being classified"
                    }
                },
                "required": ["content"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls"""
    if name == "classify_document":
        content = arguments.get("content", "")
        filename = arguments.get("filename", "document")
        
        # Validate inputs
        if not content.strip():
            return [TextContent(type="text", text="INVALID_DOCUMENT")]
        
        prompt = f"""
You are a lenient document classifier for real estate documents. Try your best to classify this document into EXACTLY one of these 3 categories:

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
            # Check if we have valid agent configuration
            if not agent_id or not agent_alias_id:
                return [TextContent(type="text", text="INVALID_DOCUMENT")]
                
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
                
                # Validate the classification result
                valid_categories = [
                    "Settlement Documents",
                    "Income Verifications", 
                    "Purchase Agreements",
                    "INVALID_DOCUMENT"
                ]
                
                # Clean up the result and check if it matches valid categories
                cleaned_result = result.strip()
                
                # Check for exact match first
                if cleaned_result in valid_categories:
                    return [TextContent(type="text", text=cleaned_result)]
                
                # Check for partial matches (case insensitive)
                for category in valid_categories:
                    if category.lower() in cleaned_result.lower():
                        return [TextContent(type="text", text=category)]
                
                # If no valid category found, mark as invalid
                return [TextContent(type="text", text="INVALID_DOCUMENT")]
                
            else:
                return [TextContent(type="text", text="INVALID_DOCUMENT")]
                
        except Exception as e:
            # Log error but return invalid document to maintain functionality
            return [TextContent(type="text", text="INVALID_DOCUMENT")]
    
    raise ValueError(f"Unknown tool: {name}")

async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
