#!/usr/bin/env python
"""Test Bedrock + Gemini setup."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.chains.llm import BedrockWithGeminiFallback

def test_setup():
    """Verify LLM setup is working."""
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    if not aws_access_key or not aws_secret_key:
        print("ERROR: AWS credentials not set")
        return False
    
    try:
        llm = BedrockWithGeminiFallback(
            aws_access_key=aws_access_key,
            aws_secret_key=aws_secret_key,
            bedrock_region=os.getenv("AWS_REGION", "us-east-1"),
        )
        
        print(f"LLM initialized. Active provider: {llm.active_provider}")
        
        # Simple test query
        response = llm.answer("Say 'Hello' only.")
        print(f"Test query response: {response[:50]}...")
        
        print("SUCCESS: Setup verified")
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    success = test_setup()
    sys.exit(0 if success else 1)
