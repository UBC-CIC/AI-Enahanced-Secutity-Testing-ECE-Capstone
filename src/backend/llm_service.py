import boto3
import json
from typing import Dict
from config import ENDPOINT_NAME

class LlmService:
    def __init__(self):
        self.runtime = boto3.client(
            'sagemaker-runtime',
            region_name='us-west-2'
        )
        self.endpoint_name = ENDPOINT_NAME

    async def analyze_zap_report(self, zap_report: Dict) -> str:
        messages = [
            {
                "role": "system",
                "content": "You are a security expert analyzing ZAP scan results. Provide clear, actionable insights."
            },
            {
                "role": "user", 
                "content": f"Analyze this ZAP security scan report and provide a clear, actionable summary:\n{json.dumps(zap_report, indent=2)}"
            }
        ]

        payload = {
            "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "messages": messages,
            "parameters": {
                "max_new_tokens": 1024,
                "temperature": 0.7,
                "top_p": 0.9
            }
        }

        try:
            print(f"Attempting to invoke endpoint: {self.endpoint_name}")
            print(f"Request payload: {json.dumps(payload)}")
            
            response = self.runtime.invoke_endpoint(
                EndpointName=self.endpoint_name,
                ContentType='application/json',
                Body=json.dumps(payload)
            )
            
            result = json.loads(response['Body'].read())
            print(f"Raw SageMaker response: {json.dumps(result)}")
            
            # Extract the assistant's message from the choices array
            if result.get("choices") and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"].strip()
            else:
                print("Unexpected response format:", result)
                return "LLM analysis unavailable. Unexpected response format."
            
        except Exception as e:
            print(f"LLM analysis failed with error type: {type(e)}")
            print(f"Error details: {str(e)}")
            if hasattr(e, 'response'):
                print(f"Error response: {e.response}")
            # return "LLM analysis unavailable. Please review the raw scan results." # TODO: hide error message in prod
            return f"Error details: {str(e)}"
