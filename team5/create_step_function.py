import boto3
import json
import os
from dotenv import load_dotenv

load_dotenv()

def create_kb_sync_step_function():
    """Create Step Function to sync S3 to Knowledge Base"""
    
    # Get environment variables
    aws_region = os.getenv("AWS_DEFAULT_REGION", "us-west-2")
    kb_id = os.getenv("KNOWLEDGE_BASE_ID", "")
    data_source_id = os.getenv("DATA_SOURCE_ID", "")
    
    if not kb_id or not data_source_id:
        print("❌ Missing KNOWLEDGE_BASE_ID or DATA_SOURCE_ID in environment")
        return None
    
    # Step Function definition
    definition = {
        "Comment": "Sync S3 to Knowledge Base",
        "StartAt": "StartIngestionJob",
        "States": {
            "StartIngestionJob": {
                "Type": "Task",
                "Resource": "arn:aws:states:::aws-sdk:bedrockagent:startIngestionJob",
                "Parameters": {
                    "KnowledgeBaseId": kb_id,
                    "DataSourceId": data_source_id
                },
                "Next": "WaitForCompletion"
            },
            "WaitForCompletion": {
                "Type": "Wait",
                "Seconds": 30,
                "Next": "CheckIngestionStatus"
            },
            "CheckIngestionStatus": {
                "Type": "Task",
                "Resource": "arn:aws:states:::aws-sdk:bedrockagent:getIngestionJob",
                "Parameters": {
                    "KnowledgeBaseId": kb_id,
                    "DataSourceId": data_source_id,
                    "IngestionJobId.$": "$.IngestionJob.IngestionJobId"
                },
                "Next": "IsComplete"
            },
            "IsComplete": {
                "Type": "Choice",
                "Choices": [
                    {
                        "Variable": "$.IngestionJob.Status",
                        "StringEquals": "COMPLETE",
                        "Next": "Success"
                    },
                    {
                        "Variable": "$.IngestionJob.Status",
                        "StringEquals": "FAILED",
                        "Next": "Failed"
                    }
                ],
                "Default": "WaitForCompletion"
            },
            "Success": {
                "Type": "Succeed"
            },
            "Failed": {
                "Type": "Fail",
                "Error": "IngestionJobFailed",
                "Cause": "Knowledge Base ingestion job failed"
            }
        }
    }
    
    # Create Step Function
    sfn_client = boto3.client('stepfunctions', region_name=aws_region)
    
    try:
        # Create IAM role for Step Function
        iam_client = boto3.client('iam', region_name=aws_region)
        
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "states.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:StartIngestionJob",
                        "bedrock:GetIngestionJob"
                    ],
                    "Resource": "*"
                }
            ]
        }
        
        role_name = "KBSyncStepFunctionRole"
        
        try:
            # Create role
            role_response = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="Role for KB sync Step Function"
            )
            role_arn = role_response['Role']['Arn']
            
            # Attach policy
            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName="KBSyncPolicy",
                PolicyDocument=json.dumps(policy_document)
            )
            
        except iam_client.exceptions.EntityAlreadyExistsException:
            # Role already exists, get its ARN
            role_response = iam_client.get_role(RoleName=role_name)
            role_arn = role_response['Role']['Arn']
        
        # Create Step Function
        sf_name = "KnowledgeBaseSyncStateMachine"
        
        try:
            response = sfn_client.create_state_machine(
                name=sf_name,
                definition=json.dumps(definition),
                roleArn=role_arn,
                type='STANDARD'
            )
            
            print(f"✅ Step Function created: {response['stateMachineArn']}")
            return response['stateMachineArn']
            
        except sfn_client.exceptions.StateMachineAlreadyExistsException:
            # Get existing Step Function ARN
            response = sfn_client.list_state_machines()
            for sm in response['stateMachines']:
                if sm['name'] == sf_name:
                    print(f"✅ Step Function already exists: {sm['stateMachineArn']}")
                    return sm['stateMachineArn']
        
    except Exception as e:
        print(f"❌ Error creating Step Function: {str(e)}")
        return None

if __name__ == "__main__":
    arn = create_kb_sync_step_function()
    if arn:
        print(f"\n📝 Add this to your .env file:")
        print(f"STEP_FUNCTION_ARN={arn}")