import os
import subprocess
import datetime
import asyncio
import boto3
from fastapi import FastAPI, HTTPException
from kubernetes import client, config
from config import settings

app = FastAPI()

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
    release_name = f"zap-basescan-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    namespace = "default"
    report_filename = f"zap_baseline_report_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.html"
    chart_path = "/app/zap-scan-job"

    try:
        # Trigger Helm release
        helm_command = [
            "helm", "install", release_name, chart_path,
            "--namespace", namespace,
            "--set", f"targetUrl={target_url}",
            "--set", f"zapScanJobEnabled=true",
            "--set", f"reportFilename={report_filename}"
        ]
        result = subprocess.run(helm_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Helm release failed: {result.stderr}")

        print(f"Helm release triggered. Output:\n{result.stdout}")

        # Introduce an initial delay for Helm to register resources
        await asyncio.sleep(5)

        # Wait for the Job to be registered in Kubernetes
        await wait_for_job_registration(release_name, namespace)

        # Wait for the Job to complete
        await wait_for_job_to_complete(release_name, namespace)

        # Get the associated pod and ensure it's in a valid state
        pod_name = await get_pod_for_job(release_name, namespace)

        # Copy the report from the pod
        container_path = f"/zap/wrk/{report_filename}"
        local_path = f"/tmp/{report_filename}"
        subprocess.run(
            ["kubectl", "cp", f"{namespace}/{pod_name}:{container_path}", local_path],
            check=True
        )

        # Upload the report to S3
        s3_key = f"zap-reports/{report_filename}"
        with open(local_path, "rb") as report_file:
            s3_client.upload_fileobj(report_file, settings.S3_BUCKET_NAME, s3_key)

        # Clean up the local file
        if os.path.exists(local_path):
            os.remove(local_path)

        return {
            "message": f"ZAP Baseline scan completed. Report uploaded to S3.",
            "s3_key": s3_key,
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"File not found error: {str(e)}")
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Kubectl command failed: {e.output}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

async def wait_for_job_registration(release_name: str, namespace: str):
    """Wait for the Job to be registered in Kubernetes."""
    max_retries = 15  # Retry up to 15 times
    delay_seconds = 5  # Wait 5 seconds between retries

    for attempt in range(max_retries):
        try:
            job = k8s_api.read_namespaced_job(name=release_name, namespace=namespace)
            print(f"Job '{release_name}' registered in Kubernetes: {job.metadata.name}")
            return
        except client.exceptions.ApiException as e:
            if e.status == 404:
                print(f"Attempt {attempt + 1}: Job '{release_name}' not found. Retrying in {delay_seconds} seconds...")
                await asyncio.sleep(delay_seconds)
                continue
            raise  # Raise unexpected exceptions

    raise HTTPException(status_code=500, detail=f"Job '{release_name}' was not registered in Kubernetes within the expected time.")

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

async def wait_for_job_to_complete(release_name: str, namespace: str):
    """Wait for the Job to complete with retries."""
    max_retries = 30  # Poll for up to 5 minutes
    delay_seconds = 10  # Wait 10 seconds between retries

    for attempt in range(max_retries):
        job_status = k8s_api.read_namespaced_job_status(name=release_name, namespace=namespace)
        if job_status.status.succeeded:
            print(f"Job '{release_name}' succeeded.")
            return
        elif job_status.status.failed:
            raise HTTPException(status_code=500, detail=f"ZAP Baseline Job '{release_name}' failed.")
        
        print(f"Attempt {attempt + 1}: Job is still running. Retrying in {delay_seconds} seconds...")
        await asyncio.sleep(delay_seconds)

    raise HTTPException(status_code=500, detail="Job did not complete within the expected time.")
