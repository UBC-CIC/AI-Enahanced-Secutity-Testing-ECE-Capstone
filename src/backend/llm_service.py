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
        alerts = zap_report.get("site", [{}])[0].get("alerts", [])
        all_analyses = []
        
        # Process alerts in chunks of 5
        for i in range(0, len(alerts), 5):
            chunk_report = {
                "alerts": alerts[i:i+5]  # Process 5 alerts at a time
            }

            messages = [
                {
                    "role": "system",
                    "content": f"You are a security expert analyzing part {i//5 + 1} of a ZAP scan report. Focus on key vulnerabilities and solutions."
                },
                {
                    "role": "user", 
                    "content": f"Analyze this part of the ZAP security scan report:\n{json.dumps(chunk_report, indent=2)}"
                }
            ]

            payload = {
                "model": "mistralai/Mistral-7B-Instruct-v0.3",
                "messages": messages,
                "parameters": {
                    "max_new_tokens": 2048,  # Reduced for each chunk
                    "temperature": 0.7,
                    "top_p": 0.9
                }
            }

            try:
                response = self.runtime.invoke_endpoint(
                    EndpointName=self.endpoint_name,
                    ContentType='application/json',
                    Body=json.dumps(payload)
                )
                
                result = json.loads(response['Body'].read())
                if result.get("choices") and len(result["choices"]) > 0:
                    all_analyses.append(result["choices"][0]["message"]["content"].strip())
            
            except Exception as e:
                print(f"Error processing chunk {i//5 + 1}: {str(e)}")
                continue

        # If we have multiple analyses, combine them
        if all_analyses:
            # Send one final request to summarize all analyses
            summary_messages = [
                {
                    "role": "system",
                    "content": "You are a security expert. Provide a concise summary of these security analyses."
                },
                {
                    "role": "user",
                    "content": f"Combine these security analyses into a clear, unified summary:\n{' '.join(all_analyses)}"
                }
            ]

            final_payload = {
                "model": "mistralai/Mistral-7B-Instruct-v0.3",
                "messages": summary_messages,
                "parameters": {
                    "max_new_tokens": 2048,
                    "temperature": 0.7,
                    "top_p": 0.9
                }
            }

            try:
                final_response = self.runtime.invoke_endpoint(
                    EndpointName=self.endpoint_name,
                    ContentType='application/json',
                    Body=json.dumps(final_payload)
                )
                
                final_result = json.loads(final_response['Body'].read())
                if final_result.get("choices") and len(final_result["choices"]) > 0:
                    return final_result["choices"][0]["message"]["content"].strip()
            
            except Exception as e:
                # return "\n\n".join(all_analyses)  # Fallback to concatenated analyses if summary fails
                return f"Error on report concat: {str(e)}"  # TODO: hide error on prod
        
        return "No analysis could be generated from the ZAP report."
