import boto3
import json
import os
from dotenv import load_dotenv

load_dotenv()

def setup_s3_event_trigger():
    """Set up S3 event to trigger Step Function when files are uploaded"""
    
    aws_region = os.getenv("AWS_DEFAULT_REGION", "us-west-2")
    bucket_name = os.getenv("S3_BUCKET_NAME", "")
    step_function_arn = os.getenv("STEP_FUNCTION_ARN", "")
    
    if not bucket_name or not step_function_arn:
        print("❌ Missing S3_BUCKET_NAME or STEP_FUNCTION_ARN in environment")
        return False
    
    # Create EventBridge rule
    events_client = boto3.client('events', region_name=aws_region)
    
    rule_name = "S3ToKBSyncRule"
    
    # Event pattern for S3 object creation
    event_pattern = {
        "source": ["aws.s3"],
        "detail-type": ["Object Created"],
        "detail": {
            "bucket": {
                "name": [bucket_name]
            }
        }
    }
    
    try:
        # Create EventBridge rule
        rule_response = events_client.put_rule(
            Name=rule_name,
            EventPattern=json.dumps(event_pattern),
            State='ENABLED',
            Description='Trigger KB sync when S3 objects are created'
        )
        
        # Add Step Function as target
        events_client.put_targets(
            Rule=rule_name,
            Targets=[
                {
                    'Id': '1',
                    'Arn': step_function_arn,
                    'RoleArn': f"arn:aws:iam::{boto3.client('sts').get_caller_identity()['Account']}:role/service-role/EventBridgeStepFunctionRole"
                }
            ]
        )
        
        print(f"✅ EventBridge rule created: {rule_response['RuleArn']}")
        
        # Enable S3 event notifications to EventBridge
        s3_client = boto3.client('s3', region_name=aws_region)
        
        try:
            s3_client.put_bucket_notification_configuration(
                Bucket=bucket_name,
                NotificationConfiguration={
                    'EventBridgeConfiguration': {}
                }
            )
            print(f"✅ S3 EventBridge notifications enabled for bucket: {bucket_name}")
            
        except Exception as e:
            print(f"⚠️ Could not enable S3 EventBridge notifications: {str(e)}")
            print("You may need to enable this manually in the S3 console")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up auto-sync: {str(e)}")
        return False

def create_eventbridge_role():
    """Create IAM role for EventBridge to invoke Step Function"""
    
    iam_client = boto3.client('iam')
    
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "events.amazonaws.com"
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
                    "states:StartExecution"
                ],
                "Resource": "*"
            }
        ]
    }
    
    role_name = "EventBridgeStepFunctionRole"
    
    try:
        # Create role
        iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Role for EventBridge to invoke Step Function"
        )
        
        # Attach policy
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName="StepFunctionInvokePolicy",
            PolicyDocument=json.dumps(policy_document)
        )
        
        print(f"✅ EventBridge role created: {role_name}")
        
    except iam_client.exceptions.EntityAlreadyExistsException:
        print(f"✅ EventBridge role already exists: {role_name}")

if __name__ == "__main__":
    print("🔧 Setting up Knowledge Base auto-sync...")
    
    # Create EventBridge role first
    create_eventbridge_role()
    
    # Set up S3 event trigger
    if setup_s3_event_trigger():
        print("\n✅ Auto-sync setup complete!")
        print("📝 Knowledge Base will now sync automatically when files are uploaded to S3")
    else:
        print("\n❌ Auto-sync setup failed")