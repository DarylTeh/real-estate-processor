#!/usr/bin/env python3
"""
Simple MCP Server for DynamoDB - Demo only
Not recommended for production use
"""
import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import boto3

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb', region_name='us-west-2')

app = Server("dynamodb-mcp")

@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="query_properties",
            description="Query property records from DynamoDB",
            inputSchema={
                "type": "object",
                "properties": {
                    "property_address": {"type": "string"}
                }
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "query_properties":
        table = dynamodb.Table('TEAM5_PROPERTY')
        # Simple scan for demo
        response = table.scan(Limit=5)
        return [TextContent(type="text", text=json.dumps(response['Items'], default=str))]

if __name__ == "__main__":
    asyncio.run(stdio_server(app))