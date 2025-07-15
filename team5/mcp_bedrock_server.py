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
