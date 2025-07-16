import boto3
import json
import uuid
from typing import Dict, Any, Tuple
from dynamodb_handler import DynamoDBHandler
import io
import PyPDF2
import pdfplumber
from docx import Document
from PIL import Image
import base64

class DocumentProcessor:
    def __init__(self, region_name: str, agent_id: str, agent_alias_id: str):
        self.region_name = region_name
        self.agent_id = agent_id
        self.agent_alias_id = agent_alias_id
        self.bedrock_runtime = boto3.client("bedrock-agent-runtime", region_name=region_name)
        self.dynamodb_handler = DynamoDBHandler(region_name)
    
    def extract_text_from_file(self, file_content: bytes, filename: str) -> str:
        """Extract text from different file types"""
        try:
            file_extension = filename.lower().split('.')[-1]
            
            if file_extension == 'pdf':
                return self._extract_text_from_pdf(file_content)
            elif file_extension == 'docx':
                return self._extract_text_from_docx(file_content)
            elif file_extension == 'txt':
                return file_content.decode('utf-8', errors='ignore')
            elif file_extension in ['png', 'jpg', 'jpeg']:
                # For images, we'll return a placeholder since we can't extract text without OCR
                return f"[IMAGE FILE: {filename}] - This is an image file that may contain text. Please process using OCR if text extraction is needed."
            else:
                # Try to decode as text
                return file_content.decode('utf-8', errors='ignore')
                
        except Exception as e:
            print(f"Error extracting text from {filename}: {str(e)}")
            return f"[ERROR EXTRACTING TEXT FROM {filename}] - {str(e)}"
    
    def _extract_text_from_pdf(self, file_content: bytes) -> str:
        """Extract text from PDF using pdfplumber (more reliable than PyPDF2)"""
        try:
            text = ""
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            
            if not text.strip():
                # Fallback to PyPDF2 if pdfplumber fails
                try:
                    pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                except:
                    pass
            
            return text.strip() if text.strip() else "[PDF CONTENT COULD NOT BE EXTRACTED - May be image-based or encrypted]"
            
        except Exception as e:
            return f"[ERROR READING PDF] - {str(e)}"
    
    def _extract_text_from_docx(self, file_content: bytes) -> str:
        """Extract text from DOCX file"""
        try:
            doc = Document(io.BytesIO(file_content))
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            return f"[ERROR READING DOCX] - {str(e)}"
    
    def classify_and_extract(self, file, s3_path: str = "", filename: str = "") -> Tuple[str, Dict[str, Any]]:
        """Classify document and extract structured data"""
        try:
            # Read file content safely
            if hasattr(file, 'read'):
                file_content = file.read()
                if hasattr(file, 'seek'):
                    file.seek(0)  # Reset file pointer if possible
            else:
                file_content = file
            
            # Extract text from the file based on its type
            if filename:
                extracted_text = self.extract_text_from_file(file_content, filename)
            else:
                # Fallback - try to decode as text
                try:
                    extracted_text = file_content.decode('utf-8', errors='ignore')
                except:
                    extracted_text = "[UNABLE TO EXTRACT TEXT FROM FILE]"
            
            # Check if we successfully extracted text
            if not extracted_text or len(extracted_text.strip()) < 10:
                return "Settlement Documents", {
                    'error': 'Unable to extract readable text from document',
                    'document_s3_path': s3_path,
                    'classification': "Settlement Documents",
                    'raw_content_preview': extracted_text[:500] if extracted_text else "No content"
                }
            
            # First, classify the document using extracted text
            classification_prompt = f"""
You are a document classifier for real estate documents. Classify this document into one of these categories:

1. Settlement Documents
2. Income Verifications  
3. Purchase Agreements

Respond with ONLY the exact category name.

Document Content:
{extracted_text[:3000]}
"""
            
            classification = self._call_bedrock_agent(classification_prompt)
            
            # Clean up classification response
            classification = classification.strip()
            valid_classifications = ["Settlement Documents", "Income Verifications", "Purchase Agreements"]
            if not classification or classification not in valid_classifications:
                # Try to find a match in the response
                for valid_class in valid_classifications:
                    if valid_class.lower() in classification.lower():
                        classification = valid_class
                        break
                else:
                    # Default classification if response is unclear
                    classification = "Settlement Documents"
            
            # Then extract structured data based on classification
            extraction_prompt = self._get_extraction_prompt(classification, extracted_text)
            extracted_data_str = self._call_bedrock_agent(extraction_prompt)
            
            # Parse the extracted data
            try:
                structured_data = json.loads(extracted_data_str)
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract JSON from the response
                try:
                    # Look for JSON in the response
                    start_idx = extracted_data_str.find('{')
                    end_idx = extracted_data_str.rfind('}') + 1
                    if start_idx != -1 and end_idx > start_idx:
                        json_str = extracted_data_str[start_idx:end_idx]
                        structured_data = json.loads(json_str)
                    else:
                        raise ValueError("No JSON found in response")
                except:
                    # If all JSON parsing fails, create a basic structure
                    structured_data = {
                        'raw_text': extracted_data_str,
                        'document_s3_path': s3_path,
                        'classification': classification,
                        'extracted_text_preview': extracted_text[:1000]
                    }
            
            # Add S3 path and metadata to structured data
            structured_data['document_s3_path'] = s3_path
            structured_data['classification'] = classification
            structured_data['filename'] = filename
            
            return classification, structured_data
            
        except Exception as e:
            print(f"Error in classify_and_extract: {str(e)}")
            # Return default values on error
            return "Settlement Documents", {
                'error': str(e),
                'document_s3_path': s3_path,
                'classification': "Settlement Documents",
                'filename': filename
            }
    
    def _get_extraction_prompt(self, classification: str, extracted_text: str) -> str:
        """Get extraction prompt based on document classification"""
        
        # Limit text length for the prompt
        text_content = extracted_text[:4000] if extracted_text else "No text content available"
        
        if "Income Verification" in classification:
            return f"""
Extract the following information from this income verification document and return as valid JSON:

{{
    "employee_name": "Full name of employee",
    "employer_name": "Name of employer/company",
    "annual_income": 0,
    "monthly_income": 0,
    "employment_start_date": "Start date of employment",
    "employment_status": "Employment status (full-time, part-time, etc.)",
    "job_title": "Job title/position",
    "verification_date": "Date of verification"
}}

Important: Return ONLY valid JSON. If any field is not found, use empty string for text fields or 0 for numeric fields.

Document Content:
{text_content}
"""
        
        elif "Settlement" in classification:
            return f"""
Extract the following information from this settlement document and return as valid JSON:

{{
    "buyer_name": "Name of buyer",
    "seller_name": "Name of seller", 
    "property_address": "Full property address",
    "settlement_date": "Date of settlement/closing",
    "sale_price": 0,
    "loan_amount": 0,
    "cash_to_close": 0,
    "title_company": "Title company name",
    "lender_name": "Lender/bank name",
    "real_estate_taxes": 0,
    "homeowners_insurance": 0,
    "title_insurance": 0,
    "recording_fees": 0,
    "transfer_taxes": 0
}}

Important: Return ONLY valid JSON. If any field is not found, use empty string for text fields or 0 for numeric fields.

Document Content:
{text_content}
"""
        
        elif "Purchase Agreement" in classification:
            return f"""
Extract the following information from this purchase agreement and return as valid JSON:

{{
    "buyer_name": "Name of buyer",
    "seller_name": "Name of seller",
    "property_address": "Full property address",
    "purchase_price": 0,
    "earnest_money": 0,
    "closing_date": "Scheduled closing date",
    "contract_date": "Contract/agreement date",
    "financing_type": "Type of financing (conventional, FHA, cash, etc.)",
    "loan_amount": 0,
    "down_payment": 0,
    "contingencies": "List of contingencies",
    "inspection_period": "Inspection period duration",
    "property_type": "Type of property (single family, condo, etc.)",
    "square_footage": 0,
    "bedrooms": 0,
    "bathrooms": 0,
    "lot_size": "Lot size",
    "year_built": 0
}}

Important: Return ONLY valid JSON. If any field is not found, use empty string for text fields or 0 for numeric fields.

Document Content:
{text_content}
"""
        
        else:
            return f"""
Extract any relevant real estate information from this document and return as valid JSON:

{{
    "document_type": "Type of document",
    "parties_involved": "Names of parties involved",
    "property_address": "Property address if mentioned",
    "key_dates": "Important dates mentioned",
    "financial_amounts": "Any monetary amounts mentioned",
    "summary": "Brief summary of document content"
}}

Important: Return ONLY valid JSON.

Document Content:
{text_content}
"""
    
    def _call_bedrock_agent(self, prompt: str) -> str:
        """Call Bedrock Agent with the given prompt"""
        try:
            response = self.bedrock_runtime.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=str(uuid.uuid4()),
                inputText=prompt
            )
            
            if 'completion' in response:
                completion = response['completion']
                if isinstance(completion, dict):
                    return completion.get('content', '').strip()
                else:
                    output = ""
                    for event in completion:
                        if 'chunk' in event and 'bytes' in event['chunk']:
                            output += event['chunk']['bytes'].decode('utf-8')
                    return output.strip()
            
            return ""
            
        except Exception as e:
            print(f"Error calling Bedrock Agent: {str(e)}")
            return ""
    
    def store_extracted_data(self, classification: str, data: Dict[str, Any]) -> str:
        """Store extracted data in appropriate DynamoDB table"""
        try:
            if "Income Verification" in classification:
                return self.dynamodb_handler.store_income_verification(data)
            elif "Settlement" in classification:
                return self.dynamodb_handler.store_settlement(data)
            elif "Purchase Agreement" in classification:
                # Store both purchase agreement and property data
                agreement_id = self.dynamodb_handler.store_purchase_agreement(data)
                
                # Extract property data and store separately
                property_data = {
                    'property_address': data.get('property_address', ''),
                    'property_type': data.get('property_type', ''),
                    'square_footage': data.get('square_footage', 0),
                    'bedrooms': data.get('bedrooms', 0),
                    'bathrooms': data.get('bathrooms', 0),
                    'lot_size': data.get('lot_size', ''),
                    'year_built': data.get('year_built', 0),
                    'property_value': data.get('purchase_price', 0),
                    'document_s3_path': data.get('document_s3_path', '')
                }
                
                if property_data['property_address']:  # Only store if we have an address
                    self.dynamodb_handler.store_property(property_data)
                
                # Extract owner profile data if available
                if data.get('buyer_name'):
                    owner_data = {
                        'full_name': data.get('buyer_name', ''),
                        'document_s3_path': data.get('document_s3_path', '')
                    }
                    self.dynamodb_handler.store_owner_profile(owner_data)
                
                return agreement_id
            else:
                # For unclassified documents, store basic info in owner profile
                owner_data = {
                    'document_s3_path': data.get('document_s3_path', ''),
                    'raw_extracted_data': json.dumps(data)
                }
                return self.dynamodb_handler.store_owner_profile(owner_data)
                
        except Exception as e:
            print(f"Error storing data in DynamoDB: {str(e)}")
            return ""
    
    def query_agent(self, query: str) -> tuple:
        """Query the Bedrock agent with a user question and return response with citations"""
        try:
            response = self.bedrock_runtime.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=str(uuid.uuid4()),
                inputText=query
            )
            
            output = ""
            citations = []
            
            if 'completion' in response:
                completion = response['completion']
                for event in completion:
                    if 'chunk' in event and 'bytes' in event['chunk']:
                        output += event['chunk']['bytes'].decode('utf-8')
                    elif 'trace' in event:
                        # Extract citations from trace
                        trace = event['trace']
                        if 'orchestrationTrace' in trace:
                            orch_trace = trace['orchestrationTrace']
                            if 'observation' in orch_trace:
                                obs = orch_trace['observation']
                                if 'knowledgeBaseLookupOutput' in obs:
                                    kb_output = obs['knowledgeBaseLookupOutput']
                                    if 'retrievedReferences' in kb_output:
                                        for ref in kb_output['retrievedReferences']:
                                            citation = {
                                                'content': ref.get('content', {}).get('text', ''),
                                                'location': ref.get('location', {}).get('s3Location', {}).get('uri', ''),
                                                'score': ref.get('score', 0)
                                            }
                                            citations.append(citation)
            
            return output.strip() if output else "No response received from agent", citations
            
        except Exception as e:
            return f"Error querying agent: {str(e)}", []
    
    def get_dynamodb_status(self) -> Dict[str, Any]:
        """Get status of all DynamoDB tables"""
        try:
            return self.dynamodb_handler.get_table_info()
        except Exception as e:
            return {"error": str(e)}
