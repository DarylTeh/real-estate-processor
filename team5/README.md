# Real Estate Document Classifier

A Streamlit application that uses AWS Bedrock to classify real estate documents and store them in S3 buckets.

## Features

- Upload and classify real estate documents into three categories:
  - Settlement Documents
  - Income Verifications
  - Purchase Agreements
- Automatically store classified documents in appropriate S3 folders
- Analytics dashboard showing usage statistics and costs
- Integration with AWS Bedrock Agent for intelligent document classification

## Local Development

1. Clone the repository
2. Create a `.env` file with your AWS configuration:
   ```
   AWS_DEFAULT_REGION=us-west-2
   BEDROCK_AGENT_ID=your-agent-id
   BEDROCK_AGENT_ALIAS_ID=your-agent-alias-id
   BEDROCK_KNOWLEDGE_BASE_ID=your-kb-id
   S3_BUCKET_NAME=your-s3-bucket
   ```
3. Install dependencies: `pip install -r requirements.txt`
4. Run the app: `streamlit run app.py`

## Deploying to Streamlit Cloud

1. Push your code to a GitHub repository
2. Connect your repository to Streamlit Cloud
3. In the Streamlit Cloud dashboard, add the following secrets:
   - AWS_DEFAULT_REGION
   - BEDROCK_AGENT_ID
   - BEDROCK_AGENT_ALIAS_ID
   - BEDROCK_KNOWLEDGE_BASE_ID
   - S3_BUCKET_NAME
   - aws_credentials.AWS_ACCESS_KEY_ID
   - aws_credentials.AWS_SECRET_ACCESS_KEY

4. Deploy the app

## AWS Permissions Required

The AWS credentials used need the following permissions:
- S3 bucket read/write access
- Bedrock Agent invocation permissions
- Bedrock Agent and Knowledge Base read permissions

## Important Notes

- Make sure your AWS credentials have the necessary permissions
- The S3 bucket must already exist
- The Bedrock Agent must be properly configured to classify real estate documents
