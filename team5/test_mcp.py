#!/usr/bin/env python3
"""
Test script for MCP functionality
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from mcp_client import classify_document_sync

def test_classification():
    """Test document classification"""
    
    # Test cases
    test_cases = [
        ("This is a settlement statement for a real estate transaction", "settlement.pdf"),
        ("Income verification letter from employer", "income.pdf"),
        ("Purchase agreement for residential property", "purchase.pdf"),
        ("Random text that doesn't match any category", "random.txt"),
        ("", "empty.txt")
    ]
    
    print("Testing MCP Document Classification:")
    print("=" * 50)
    
    for content, filename in test_cases:
        print(f"\nTesting: {filename}")
        print(f"Content: {content[:50]}...")
        result = classify_document_sync(content, filename)
        print(f"Result: {result}")
        
        # Validate result
        valid_categories = ["Settlement Documents", "Income Verifications", "Purchase Agreements", "INVALID_DOCUMENT"]
        if result in valid_categories:
            print("✅ Valid classification")
        else:
            print("❌ Invalid classification")

if __name__ == "__main__":
    test_classification()
