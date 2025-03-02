import boto3
import json
import time
import datetime
import prompts
import logging
from fastapi import HTTPException
from botocore.exceptions import ClientError
from fastapi import HTTPException
# from config import settings # TODO: temp comment out. Please uncomment me if needed @Anderw!

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Bedrock clients
try:
    bedrock_client = boto3.client("bedrock", region_name="us-west-2")
    bedrock_runtime_client = boto3.client("bedrock-runtime", region_name="us-west-2")
except BotoCoreError as e:
    logger.error(f"Failed to initialize AWS Bedrock clients: {e}")
    raise RuntimeError("AWS Bedrock client initialization failed.") from e

# Define mode-specific fields to remove
mode_specific_fields = {
    "chat": ["instances", "pluginid", "alertRef", "wascid", "sourceid", "cweid", "otherinfo", "sequences", "@programName", "@version", "@port", "@ssl"],  
    "report": ["instances", "pluginid", "alertRef", "wascid", "sourceid", "cweid", "otherinfo", "sequences", "@programName", "@version", "@port", "@ssl"],
}

#Define available modes and their corresponding prompts
mode_prompts = {
    "chat": prompts.CYBERSECURITY_PROMPT_TEMPLATE_CHAT,
    "report": prompts.CYBERSECURITY_PROMPT_TEMPLATE_REPORT,
    # Future modes can be easily added here
}

def list_bedrock_models():
    """List available AWS Bedrock foundation models"""
    try:
        return bedrock_client.list_foundation_models()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing Bedrock models: {str(e)}")

def clean_report(data, fields_to_remove):
    if isinstance(data, dict):
        return {k: clean_report(v, fields_to_remove) for k, v in data.items() if k not in fields_to_remove}
    elif isinstance(data, list):
        return [clean_report(i, fields_to_remove) for i in data]
    return data


def generate_prompt(mode: str, input_text: str, input_report: str):
    """Generates the appropriate prompt based on the selected mode."""

    if mode not in mode_prompts:
        raise HTTPException(status_code=400, detail=f"Invalid mode '{mode}'. Available modes: {list(MODE_PROMPTS.keys())}.")

    # Validate inputs before proceeding
    missing_inputs = []
    if not input_text and mode == "chat":
        missing_inputs.append("input_text")
    if not input_report:
        missing_inputs.append("input_report")

    if missing_inputs:
        logger.warning(f"Missing inputs: {missing_inputs}")
        raise HTTPException(status_code=400, detail=f"Missing required input(s): {', '.join(missing_inputs)}")

    # Select appropriate fields for cleaning
    fields_to_remove = mode_specific_fields.get(mode, [])

    # Attempt to clean input report
    try:
        clean_input_report = clean_report(json.loads(input_report), fields_to_remove)
        formatted_report = json.dumps(clean_input_report, indent=2)
    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError: Invalid input_report - {e}")
        raise HTTPException(status_code=400, detail="Invalid input_report. Expected a JSON-formatted string.")

    # Define mode behavior dynamically
    mode_templates = {
        "chat": lambda: mode_prompts["chat"].format(input_report=formatted_report, input_text=input_text),
        "report": lambda: mode_prompts["report"].format(input_report=formatted_report),
    }

    # Generate response based on mode
    return mode_templates.get(mode, lambda: {"error": f"Invalid mode '{mode}'. Available modes: {list(mode_prompts.keys())}."})()


def invoke_bedrock_model(input_text: str):
    """Invoke the Amazon Titan Text Express model with the given input text."""
    try:
        # Prepare the request payload
        body = json.dumps({
            "prompt": input_text,  
            "temperature": 0.7,
            "top_p": 0.9,
            "max_gen_len": 1500
        })

        # Invoke the model
        response = bedrock_runtime_client.invoke_model(
            # modelId=settings.BASE_MODEL_ID,
            modelId="amazon.titan-text-express-v1",  # TODO: temp value. Please update me @Andrew!
            contentType="application/json",
            accept="application/json",
            body=body
        )

            # Parse the response
        response_body = json.loads(response["body"].read())

        # Ensure the response contains the expected field
        if "generation" not in response_body:
            logger.error("Missing 'generation' field in Bedrock response.")
            raise HTTPException(status_code=500, detail="Invalid response from Bedrock model.")

        return response_body["generation"]

    except ClientError as e:
            logger.error(f"ClientError while invoking Bedrock model: {e}")
            raise HTTPException(status_code=500, detail="AWS Bedrock request failed.")
    except json.JSONDecodeError as e:
            logger.error(f"JSONDecodeError in response parsing: {e}")
            raise HTTPException(status_code=500, detail="Malformed response from Bedrock model.")
    except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise HTTPException(status_code=500, detail="Unexpected error while invoking Bedrock model.")

