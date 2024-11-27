import os
import subprocess
import datetime
import asyncio
import boto3
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from kubernetes import client, config
from config import settings
from urllib.parse import urlparse

app = FastAPI()

# Allow all origins for now for local testing (prevents CORS errors)
# TODO: Review and update origins once we are ready to deploy
origins = [
    "http://localhost:3000",  # Frontend local testing
    "http://localhost:8000",  # FastAPI local testing
    "http://localhost",  # Default http
    "https://localhost",  # Default https
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware to handle long-running requests
# This is needed since our scans can take a long time to complete
class TimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await asyncio.wait_for(call_next(request), timeout=1800)
            return response
        except asyncio.TimeoutError:
            return Response(
                content=json.dumps({
                    "detail": "Request timeout exceeded"
                }),
                status_code=504,
                media_type="application/json"
            )

app.add_middleware(TimeoutMiddleware)

# Load Kubernetes config
config.load_incluster_config()

k8s_api = client.BatchV1Api()
core_v1_api = client.CoreV1Api()
s3_client = boto3.client("s3", region_name="us-west-2")

@app.get("/")
async def root():
    return {"message": "Hello, world!"}

@app.post("/zap/basescan")
async def zap_basescan(target_url: str):
    # Validate URL
    try:
        result = urlparse(target_url)
        if not all([result.scheme, result.netloc]):
            raise HTTPException(
                status_code=400, 
                detail="Invalid URL format. Must include scheme (http/https)"
            )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL format")

    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    values_job_name = "zap-basescan-job"
    release_name = f"zap-basescan-{timestamp}"
    job_name = f"{values_job_name}-{timestamp}"
    namespace = "default"
    chart_path = "/app/zap-scan-job"

    try:
        # Trigger Helm release with timestamp
        helm_command = [
            "helm", "install", release_name, chart_path,
            "--namespace", namespace,
            "--set", f"targetUrl={target_url}",
            "--set", "zapScanJobEnabled=true",
            "--set", f"job.name={values_job_name}",
            "--set", f"job.timestamp={timestamp}"
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
        await wait_for_job_to_complete(job_name, namespace, timestamp)

        # Get report
        pod_name = await get_pod_for_job(job_name, namespace)
        report_filename = f"{timestamp}-report.json"
        
        scan_results = await get_zap_report(report_filename)
        return scan_results

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

async def wait_for_job_to_complete(job_name: str, namespace: str, timestamp: str):
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
                report_filename = f"{timestamp}-report.json"
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
