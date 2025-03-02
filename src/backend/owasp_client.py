import datetime
import json
import subprocess
import asyncio
import logging
import boto3
import uuid
import os
import sys
from fastapi import HTTPException
from kubernetes import client, config
from urllib.parse import urlparse
import bedrock_client

# Load Kubernetes config
config.load_incluster_config()
k8s_api = client.BatchV1Api()
core_v1_api = client.CoreV1Api()

# Initialize S3 client
s3_client = boto3.client("s3", region_name="us-west-2")
BUCKET_NAME = "s3stack-aestbucket11161ed0-oyzazupebp7h"

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Remove the running_scans dictionary
# Instead, we'll track scan state in S3 and through Kubernetes jobs

async def start_zap_basescan(target_url: str):
    """Start a ZAP baseline scan as a background task and return the scan ID immediately"""
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    unique_id = str(uuid.uuid4())[:8]  # Use first 8 characters of UUID for brevity
    scan_id = f"{timestamp}-{unique_id}"
    values_job_name = "zap-basescan-job"
    release_name = f"zap-basescan-{scan_id}"
    job_name = f"{values_job_name}-{scan_id}"
    namespace = "default"
    chart_path = "/app/zap-scan-job"
    
    # Verify the chart path exists
    if not os.path.exists(chart_path):
        logger.error(f"Chart path does not exist: {chart_path}")
        # Try to list files in the /app directory to see what's available
        try:
            app_files = os.listdir("/app")
            logger.info(f"Files in /app directory: {app_files}")
        except Exception as e:
            logger.error(f"Could not list files in /app: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ZAP chart path not found: {chart_path}")
    
    logger.info(f"Starting ZAP scan for {target_url} with ID {scan_id}")
    
    # Store initial scan status in S3
    status_data = {
        "scan_id": scan_id,
        "status": "initiated",
        "target_url": target_url,
        "timestamp": timestamp,
        "unique_id": unique_id,
        "job_name": job_name,
        "release_name": release_name,
        "created_at": datetime.datetime.now().isoformat()
    }
    
    # Upload initial status to S3
    status_key = f"scan-status/{scan_id}.json"
    try:
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=status_key,
            Body=json.dumps(status_data),
            ContentType="application/json"
        )
        logger.info(f"Uploaded initial status to S3 for scan ID: {scan_id}")
    except Exception as e:
        logger.error(f"Failed to upload status to S3: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize scan in S3: {str(e)}")
    
    # Start the scan process in the background without awaiting completion
    background_task = asyncio.create_task(
        execute_zap_scan(
            scan_id=scan_id,
            target_url=target_url,
            timestamp=timestamp,
            job_name=job_name,
            release_name=release_name,
            namespace=namespace,
            chart_path=chart_path
        )
    )
    
    # Add error handler to the background task
    background_task.add_done_callback(lambda t: handle_task_result(t, scan_id))
    
    return scan_id

def handle_task_result(task, scan_id):
    """Handle results from background tasks to ensure errors are logged"""
    try:
        # Check if the task raised an exception
        exception = task.exception()
        if exception:
            logger.error(f"Background task for scan {scan_id} failed with exception: {exception}")
            # We could also update the scan status in S3 here, but the execute_zap_scan function
            # should already handle that if possible
    except asyncio.CancelledError:
        logger.warning(f"Background task for scan {scan_id} was cancelled")
    except Exception as e:
        logger.error(f"Error handling background task result for scan {scan_id}: {str(e)}")

async def execute_zap_scan(scan_id, target_url, timestamp, job_name, release_name, namespace, chart_path):
    """Execute the ZAP scan as a background task"""
    try:
        # Update status to running in S3
        await update_scan_status(scan_id, "running")
        
        # First, check if the chart path exists
        if not os.path.exists(chart_path):
            error_msg = f"Chart path does not exist: {chart_path}"
            logger.error(error_msg)
            await update_scan_status(scan_id, "failed", error=error_msg)
            return
            
        logger.info(f"Starting ZAP scan for {target_url} with ID {scan_id}")
        logger.info(f"Using chart path: {chart_path}")
        
        # Trigger Helm release with explicit job name
        helm_command = [
            "helm", "install", release_name, chart_path,
            "--namespace", namespace,
            "--set", f"targetUrl={target_url}",
            "--set", "zapScanJobEnabled=true",
            "--set", f"job.name={job_name}",  # Use job.name instead of job.fullName to match the Helm template
            "--set", f"job.timestamp={scan_id}"   # Still pass timestamp for report naming
        ]
        
        logger.info(f"Executing Helm command: {' '.join(helm_command)}")
        
        result = subprocess.run(
            helm_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            error_msg = f"Helm release failed: {result.stderr}"
            logger.error(error_msg)
            await update_scan_status(scan_id, "failed", error=error_msg)
            return

        logger.info(f"Helm release triggered successfully for {scan_id}. Output:\n{result.stdout}")

        # Wait for job completion
        try:
            await wait_for_job_registration(job_name, namespace)
            await wait_for_job_to_complete(job_name, namespace, scan_id)
            
            # Update status to completed
            await update_scan_status(scan_id, "completed")
            
        except Exception as e:
            error_msg = f"Job execution failed: {str(e)}"
            logger.error(error_msg)
            await update_scan_status(scan_id, "failed", error=error_msg)

    except Exception as e:
        error_msg = f"Scan execution failed: {str(e)}"
        logger.error(error_msg)
        await update_scan_status(scan_id, "failed", error=error_msg)

async def update_scan_status(scan_id, status, error=None):
    """Update the scan status in S3"""
    try:
        # First, try to get existing status
        status_key = f"scan-status/{scan_id}.json"
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
            status_data = json.loads(response['Body'].read().decode('utf-8'))
        except s3_client.exceptions.NoSuchKey:
            # Create a new status object if one doesn't exist
            status_data = {
                "scan_id": scan_id,
                "created_at": datetime.datetime.now().isoformat()
            }
        
        # Update the status
        status_data["status"] = status
        status_data["updated_at"] = datetime.datetime.now().isoformat()
        
        if error:
            status_data["error"] = error
        
        # Write back to S3
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=status_key,
            Body=json.dumps(status_data),
            ContentType="application/json"
        )
        
        return status_data
    except Exception as e:
        print(f"Failed to update scan status in S3: {str(e)}")
        # Continue execution even if status update fails

async def check_scan_status(scan_id: str):
    """Check the status of a scan and return report if available"""
    # First, check if the report exists in S3
    report_key = f"{scan_id}-report.json"
    status_key = f"scan-status/{scan_id}.json"
    
    try:
        # Check if the final report exists
        try:
            s3_client.head_object(Bucket=BUCKET_NAME, Key=report_key)
            # If we're here, the report exists
            report_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=report_key)
            report_data = json.loads(report_response['Body'].read().decode('utf-8'))
            
            # Process with Bedrock for AI analysis
            ai_analysis = await process_report_with_ai(report_data)
            
            return {
                "scan_id": scan_id,
                "status": "completed",
                "message": "Scan completed successfully",
                "report": report_data,
                "ai_analysis": ai_analysis
            }
        except s3_client.exceptions.NoSuchKey:
            # Report doesn't exist yet, check the status file
            pass
        
        # Check the status file
        try:
            status_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
            status_data = json.loads(status_response['Body'].read().decode('utf-8'))
            
            status = status_data.get("status", "unknown")
            
            if status == "failed":
                return {
                    "scan_id": scan_id,
                    "status": status,
                    "message": "Scan failed",
                    "error": status_data.get("error", "Unknown error")
                }
            elif status in ["initiated", "running"]:
                # Also check Kubernetes job status for more accurate information
                job_name = status_data.get("job_name")
                if job_name:
                    try:
                        job = k8s_api.read_namespaced_job(name=job_name, namespace="default")
                        job_status = "unknown"
                        
                        if job.status.succeeded:
                            job_status = "succeeded"
                            # If job succeeded but no report yet, it's still processing
                            return {
                                "scan_id": scan_id,
                                "status": "processing",
                                "message": "Scan completed, generating report"
                            }
                        elif job.status.failed:
                            job_status = "failed"
                            await update_scan_status(scan_id, "failed", error="Kubernetes job failed")
                            return {
                                "scan_id": scan_id,
                                "status": "failed",
                                "message": "Scan job failed in Kubernetes"
                            }
                        elif job.status.active:
                            job_status = "active"
                    except client.exceptions.ApiException:
                        # Job might not exist yet
                        job_status = "pending"
                        
                    return {
                        "scan_id": scan_id,
                        "status": status,
                        "job_status": job_status,
                        "message": "Scan is in progress"
                    }
                
                return {
                    "scan_id": scan_id,
                    "status": status,
                    "message": "Scan is in progress"
                }
            else:
                return {
                    "scan_id": scan_id,
                    "status": status,
                    "message": f"Scan status: {status}"
                }
                
        except s3_client.exceptions.NoSuchKey:
            # Neither report nor status file exists
            return {
                "scan_id": scan_id,
                "status": "not_found",
                "message": "Scan not found"
            }
            
    except Exception as e:
        return {
            "scan_id": scan_id,
            "status": "error",
            "message": f"Error retrieving scan status: {str(e)}"
        }

async def process_report_with_ai(report_data):
    """Process the ZAP report with Bedrock for AI analysis"""
    try:
        # Convert report to string for the AI model
        report_json_str = json.dumps(report_data)
        
        # Generate prompt for report analysis
        prompt = bedrock_client.generate_prompt("report", "", report_json_str)
        
        # Invoke Bedrock model
        ai_analysis = bedrock_client.invoke_bedrock_model(prompt)
        
        return ai_analysis
    except Exception as e:
        logging.error(f"Error processing report with AI: {str(e)}")
        return f"AI analysis failed: {str(e)}"

async def zap_basescan(target_url: str):
    """Legacy synchronous ZAP scan function (kept for compatibility)"""
    # This function remains unchanged for backward compatibility
    # but we'll redirect it to use the new async approach

    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    unique_id = str(uuid.uuid4())[:8]  # Use first 8 characters of UUID for brevity
    scan_id = f"{timestamp}-{unique_id}"
    values_job_name = "zap-basescan-job"
    release_name = f"zap-basescan-{scan_id}"
    job_name = f"{values_job_name}-{scan_id}"
    namespace = "default"
    chart_path = "/app/zap-scan-job"

    try:
        # Trigger Helm release with timestamp
        helm_command = [
            "helm", "install", release_name, chart_path,
            "--namespace", namespace,
            "--set", f"targetUrl={target_url}",
            "--set", "zapScanJobEnabled=true",
            "--set", f"job.name={job_name}",
            "--set", f"job.timestamp={scan_id}"
        ]
        result = subprocess.run(
            helm_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Helm release failed: {result.stderr}")

        print(f"Helm release triggered. Output:\n{result.stdout}")

        # Wait for job completion
        await wait_for_job_registration(job_name, namespace)
        await wait_for_job_to_complete(job_name, namespace, scan_id)  # Use scan_id instead of timestamp

        # Get report
        pod_name = await get_pod_for_job(job_name, namespace)
        report_filename = f"{scan_id}-report.json"  # Use scan_id for report filename
        
        scan_results = await get_zap_report(report_filename)
        return scan_results # TODO: For now , leave it as it is since I'll turn off LLM frequently

        # ai_analysis = await llm_service.analyze_zap_report(scan_results)

        # return {
        #     "ai_analysis": ai_analysis,
        #     "scan_results": scan_results,
        #     "metadata": {
        #         "timestamp": timestamp,
        #         "target_url": target_url,
        #     }
        # }

        # # File clean up. Not enabled atm.
        # finally:
        #     # File deletion
        #     report_path = f"/reports/{report_filename}"
        #     if os.path.exists(report_path):
        #         os.remove(report_path)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Scan failed: {str(e)}",
                "job_name": job_name,
                "timestamp": timestamp,
                "target_url": target_url
            }
        )

async def wait_for_job_registration(job_name: str, namespace: str):
    """Wait for the Job to be registered in Kubernetes."""
    max_retries = 15
    delay_seconds = 5

    for attempt in range(max_retries):
        try:
            print(f"Attempting to find job '{job_name}' in namespace '{namespace}'")
            jobs = k8s_api.list_namespaced_job(namespace=namespace)
            print(f"Found jobs: {[job.metadata.name for job in jobs.items]}")
            
            job = k8s_api.read_namespaced_job(name=job_name, namespace=namespace)
            print(f"Job '{job_name}' registered in Kubernetes: {job.metadata.name}")
            return
        except client.exceptions.ApiException as e:
            if e.status == 404:
                print(f"Attempt {attempt + 1}: Job '{job_name}' not found. Retrying in {delay_seconds} seconds...")
                await asyncio.sleep(delay_seconds)
                continue
            raise

    raise HTTPException(status_code=500, detail=f"Job '{job_name}' was not registered in Kubernetes within the expected time.")

async def get_pod_for_job(job_name: str, namespace: str) -> str:
    """Get the pod associated with a specific Job."""
    max_retries = 10  # Retry up to 10 times
    delay_seconds = 5  # Start with a 5-second delay

    for attempt in range(max_retries):
        pods = core_v1_api.list_namespaced_pod(
            namespace=namespace,
            label_selector=f"job-name={job_name}"
        )
        if pods.items:
            pod_name = pods.items[0].metadata.name
            pod_status = pods.items[0].status.phase
            if pod_status in ("Running", "Succeeded"):
                print(f"Pod for job '{job_name}' found: {pod_name}")
                return pod_name
            else:
                print(f"Pod '{pod_name}' for job '{job_name}' is in state '{pod_status}'. Retrying...")
        
        print(f"Attempt {attempt + 1}: Pod for job '{job_name}' not found. Retrying in {delay_seconds} seconds...")
        await asyncio.sleep(delay_seconds)

    raise HTTPException(status_code=500, detail=f"No pod found for job '{job_name}' within the expected time.")

async def wait_for_job_to_complete(job_name: str, namespace: str, scan_id: str):
    max_retries = 60
    delay_seconds = 10

    for attempt in range(max_retries):
        try:
            job_status = k8s_api.read_namespaced_job_status(name=job_name, namespace=namespace)
            pod_name = await get_pod_for_job(job_name, namespace)
            pod = core_v1_api.read_namespaced_pod(name=pod_name, namespace=namespace)

            # Check pod phase
            if pod.status.phase in ["Succeeded", "Failed"]:
                logs = core_v1_api.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=namespace
                )
                
                # Check for successful report generation with correct filename
                report_filename = f"{scan_id}-report.json"
                if f"Job report generated report /zap/wrk/{report_filename}" in logs:
                    print(f"ZAP scan completed and report generated for job '{job_name}'")
                    
                    # Sleep for 2 seconds to ensure the file is fully written
                    await asyncio.sleep(2)
                    
                    if "FAIL-NEW: 0" in logs:
                        print("ZAP scan completed with no failures")
                    else:
                        print("ZAP scan completed with warnings (but no failures)")
                    
                    return
                else:
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "message": "ZAP scan failed to generate report",
                            "logs": logs,
                            "job_name": job_name,
                            "pod_name": pod_name
                        }
                    )

            print(f"Attempt {attempt + 1}: Job is still running. Retrying in {delay_seconds} seconds...")
            await asyncio.sleep(delay_seconds)
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": f"Failed to check job status: {str(e)}",
                    "job_name": job_name
                }
            )

    raise HTTPException(
        status_code=500,
        detail=f"Job '{job_name}' did not complete within the expected time."
    )

async def get_zap_report(report_filename: str):
    max_retries = 3
    delay_seconds = 5
    
    for attempt in range(max_retries):
        try:
            report_path = f"/reports/{report_filename}"
            with open(report_path, 'r') as f:
                report_data = json.loads(f.read())
            
            # # Clean up report file after successful read, or we can set S3 to remove files after a certain time
            # try:
            #     os.remove(report_path)
            #     print(f"Deleted report file: {report_path}")
            # except Exception as cleanup_error:
            #     print(f"Failed to delete report file (non-fatal): {cleanup_error}")
                
            return report_data
                
        except (FileNotFoundError, json.JSONDecodeError) as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(delay_seconds)
                continue
            raise HTTPException(
                status_code=500,
                detail=f"Error reading report: {str(e)}"
            )
