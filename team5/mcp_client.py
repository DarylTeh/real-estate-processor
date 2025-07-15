"""
MCP Client for Streamlit app
"""
import asyncio
import json
import subprocess
import sys
from typing import Optional

class MCPClient:
    def __init__(self):
        self.process = None
        self.initialized = False
    
    async def start_server(self):
        """Start the MCP server process"""
        if self.process is None:
            self.process = await asyncio.create_subprocess_exec(
                sys.executable, "mcp_bedrock_server.py",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Initialize the server
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "clientInfo": {
                        "name": "streamlit-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            await self._send_request(init_request)
            self.initialized = True
    
    async def _send_request(self, request):
        """Send a request to the MCP server"""
        if not self.process:
            await self.start_server()
        
        request_str = json.dumps(request) + "\n"
        self.process.stdin.write(request_str.encode())
        await self.process.stdin.drain()
        
        # Read response
        response_line = await self.process.stdout.readline()
        if response_line:
            return json.loads(response_line.decode().strip())
        return None
    
    async def classify_document(self, content: str, filename: str = "document") -> str:
        """Classify a document using the MCP server"""
        if not self.initialized:
            await self.start_server()
        
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "classify_document",
                "arguments": {
                    "content": content,
                    "filename": filename
                }
            }
        }
        
        try:
            response = await self._send_request(request)
            if response and "result" in response:
                content_list = response["result"].get("content", [])
                if content_list and len(content_list) > 0:
                    return content_list[0].get("text", "No classification returned")
            return "Error: Invalid response format"
        except Exception as e:
            return f"Error: {str(e)}"
    
    async def close(self):
        """Close the MCP server process"""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            self.process = None
            self.initialized = False

# Global MCP client instance
mcp_client = MCPClient()

def classify_document_sync(content: str, filename: str = "document") -> str:
    """Synchronous wrapper for document classification"""
    try:
        # Try to get existing event loop
        try:
            loop = asyncio.get_running_loop()
            # If we're in an existing loop, create a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, mcp_client.classify_document(content, filename))
                return future.result()
        except RuntimeError:
            # No running loop, safe to use asyncio.run
            return asyncio.run(mcp_client.classify_document(content, filename))
    except Exception as e:
        return f"INVALID_DOCUMENT"
