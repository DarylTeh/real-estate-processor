import boto3
import json
import uuid
import random
from datetime import datetime
from typing import Dict, Any, Optional
import os

class DynamoDBHandler:
    def __init__(self, region_name: str = None):
        self.region_name = region_name or os.getenv("AWS_DEFAULT_REGION", "us-west-2")
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region_name)
        self.dynamodb_client = boto3.client('dynamodb', region_name=self.region_name)
        
        # Table references
        self.tables = {
            'income_verification': self.dynamodb.Table('TEAM5_INCOME_VERIFICATION'),
            'owner_profile': self.dynamodb.Table('TEAM5_OWNER_PROFILE'),
            'property': self.dynamodb.Table('TEAM5_PROPERTY'),
            'purchase_agreement': self.dynamodb.Table('TEAM5_PURCHASE_AGREEMENT'),
            'settlement': self.dynamodb.Table('TEAM5_SETTLEMENT')
        }
    
    def store_income_verification(self, data: Dict[str, Any]) -> str:
        """Store income verification data
        Schema: BUYER_ID (Hash), NAME (Range)
        """
        buyer_id = str(uuid.uuid4())
        name = data.get('employee_name', 'Unknown Employee')
        if not name or name.strip() == '':
            name = 'Unknown Employee'
        
        item = {
            'BUYER_ID': buyer_id,  # Primary key (Hash)
            'NAME': name,          # Sort key (Range)
            'timestamp': datetime.utcnow().isoformat(),
            'employee_name': data.get('employee_name', ''),
            'employer_name': data.get('employer_name', ''),
            'annual_income': str(data.get('annual_income', 0)),
            'monthly_income': str(data.get('monthly_income', 0)),
            'employment_start_date': data.get('employment_start_date', ''),
            'employment_status': data.get('employment_status', ''),
            'job_title': data.get('job_title', ''),
            'document_s3_path': data.get('document_s3_path', ''),
            'verification_date': data.get('verification_date', ''),
            'raw_extracted_data': json.dumps(data)
        }
        
        self.tables['income_verification'].put_item(Item=item)
        return buyer_id
    
    def store_owner_profile(self, data: Dict[str, Any]) -> str:
        """Store owner profile data
        Schema: OWNER_ID (Hash), OWNER_NAME (Range)
        """
        owner_id = str(uuid.uuid4())
        owner_name = data.get('full_name', data.get('buyer_name', 'Unknown Owner'))
        if not owner_name or owner_name.strip() == '':
            owner_name = 'Unknown Owner'
        
        item = {
            'OWNER_ID': owner_id,     # Primary key (Hash)
            'OWNER_NAME': owner_name, # Sort key (Range)
            'timestamp': datetime.utcnow().isoformat(),
            'full_name': data.get('full_name', ''),
            'first_name': data.get('first_name', ''),
            'last_name': data.get('last_name', ''),
            'email': data.get('email', ''),
            'phone': data.get('phone', ''),
            'address': data.get('address', ''),
            'city': data.get('city', ''),
            'state': data.get('state', ''),
            'zip_code': data.get('zip_code', ''),
            'ssn_last_four': data.get('ssn_last_four', ''),
            'date_of_birth': data.get('date_of_birth', ''),
            'document_s3_path': data.get('document_s3_path', ''),
            'raw_extracted_data': json.dumps(data)
        }
        
        self.tables['owner_profile'].put_item(Item=item)
        return owner_id
    
    def store_property(self, data: Dict[str, Any]) -> str:
        """Store property data
        Schema: PROPERTY_ID (Hash), SINGPOST (Range)
        """
        property_id = str(uuid.uuid4())
        # Use property address or a default value for SINGPOST
        singpost = data.get('property_address', 'Unknown Address')[:50]  # Truncate if too long
        if not singpost or singpost.strip() == '':
            singpost = 'Unknown Address'
        
        item = {
            'PROPERTY_ID': property_id,  # Primary key (Hash)
            'SINGPOST': singpost,        # Sort key (Range)
            'timestamp': datetime.utcnow().isoformat(),
            'property_address': data.get('property_address', ''),
            'city': data.get('city', ''),
            'state': data.get('state', ''),
            'zip_code': data.get('zip_code', ''),
            'property_type': data.get('property_type', ''),
            'square_footage': str(data.get('square_footage', 0)),
            'bedrooms': str(data.get('bedrooms', 0)),
            'bathrooms': str(data.get('bathrooms', 0)),
            'lot_size': data.get('lot_size', ''),
            'year_built': str(data.get('year_built', 0)),
            'property_value': str(data.get('property_value', 0)),
            'apn': data.get('apn', ''),  # Assessor's Parcel Number
            'document_s3_path': data.get('document_s3_path', ''),
            'raw_extracted_data': json.dumps(data)
        }
        
        self.tables['property'].put_item(Item=item)
        return property_id
    
    def store_purchase_agreement(self, data: Dict[str, Any]) -> str:
        """Store purchase agreement data
        Schema: AGREEMENT_ID (Hash - Number), PROPERTY_ID (Range - Number)
        """
        # Generate numeric IDs as the schema expects numbers
        agreement_id = random.randint(100000, 999999)
        property_id = random.randint(100000, 999999)
        
        item = {
            'AGREEMENT_ID': agreement_id,  # Primary key (Hash - Number)
            'PROPERTY_ID': property_id,    # Sort key (Range - Number)
            'timestamp': datetime.utcnow().isoformat(),
            'buyer_name': data.get('buyer_name', ''),
            'seller_name': data.get('seller_name', ''),
            'property_address': data.get('property_address', ''),
            'purchase_price': str(data.get('purchase_price', 0)),
            'earnest_money': str(data.get('earnest_money', 0)),
            'closing_date': data.get('closing_date', ''),
            'contract_date': data.get('contract_date', ''),
            'financing_type': data.get('financing_type', ''),
            'loan_amount': str(data.get('loan_amount', 0)),
            'down_payment': str(data.get('down_payment', 0)),
            'contingencies': data.get('contingencies', ''),
            'inspection_period': data.get('inspection_period', ''),
            'document_s3_path': data.get('document_s3_path', ''),
            'raw_extracted_data': json.dumps(data)
        }
        
        self.tables['purchase_agreement'].put_item(Item=item)
        return str(agreement_id)
    
    def store_settlement(self, data: Dict[str, Any]) -> str:
        """Store settlement data
        Schema: SETTLEMENT_ID (Hash - String), PROPERTY_ID (Range - Number)
        """
        settlement_id = str(uuid.uuid4())
        property_id = random.randint(100000, 999999)
        
        item = {
            'SETTLEMENT_ID': settlement_id,  # Primary key (Hash - String)
            'PROPERTY_ID': property_id,      # Sort key (Range - Number)
            'timestamp': datetime.utcnow().isoformat(),
            'buyer_name': data.get('buyer_name', ''),
            'seller_name': data.get('seller_name', ''),
            'property_address': data.get('property_address', ''),
            'settlement_date': data.get('settlement_date', ''),
            'sale_price': str(data.get('sale_price', 0)),
            'loan_amount': str(data.get('loan_amount', 0)),
            'cash_to_close': str(data.get('cash_to_close', 0)),
            'title_company': data.get('title_company', ''),
            'lender_name': data.get('lender_name', ''),
            'real_estate_taxes': str(data.get('real_estate_taxes', 0)),
            'homeowners_insurance': str(data.get('homeowners_insurance', 0)),
            'title_insurance': str(data.get('title_insurance', 0)),
            'recording_fees': str(data.get('recording_fees', 0)),
            'transfer_taxes': str(data.get('transfer_taxes', 0)),
            'document_s3_path': data.get('document_s3_path', ''),
            'raw_extracted_data': json.dumps(data)
        }
        
        self.tables['settlement'].put_item(Item=item)
        return settlement_id
    
    def get_table_info(self) -> Dict[str, Any]:
        """Get information about all tables"""
        info = {}
        for table_name, table in self.tables.items():
            try:
                # Use the client to describe table instead of table resource
                table_full_name = table.name
                response = self.dynamodb_client.describe_table(TableName=table_full_name)
                info[table_name] = {
                    'status': response['Table']['TableStatus'],
                    'item_count': response['Table']['ItemCount'],
                    'size_bytes': response['Table']['TableSizeBytes']
                }
            except Exception as e:
                info[table_name] = {'error': str(e)}
        return info
    
    def query_recent_records(self, table_name: str, limit: int = 10) -> list:
        """Query recent records from a specific table"""
        try:
            if table_name not in self.tables:
                return []
            
            table = self.tables[table_name]
            response = table.scan(Limit=limit)
            return response.get('Items', [])
        except Exception as e:
            print(f"Error querying {table_name}: {str(e)}")
            return []
