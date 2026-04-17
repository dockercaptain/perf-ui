from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from kubernetes import client, config
import uuid

app = FastAPI()

class K6Script(BaseModel):
    script: str  # JavaScript code for k6

@app.post("/run-k6")
def run_k6_test(payload: K6Script):
    try:
      # config.load_kube_config()  # Or use load_incluster_config() if running inside cluster
        config.load_kube_config(config_file="uat.kubeconfig")
 
        job_name = f"k6-job-{uuid.uuid4().hex[:6]}"
        script_configmap_name = f"{job_name}-script"

        # 1. Create ConfigMap with the script
        v1 = client.CoreV1Api()
        v1.create_namespaced_config_map(
            namespace="default",
            body=client.V1ConfigMap(
                metadata=client.V1ObjectMeta(name=script_configmap_name),
                data={"script.js": payload.script}
            )
        )

        # 2. Define the k6 Job
        batch_v1 = client.BatchV1Api()
        job = client.V1Job(
            metadata=client.V1ObjectMeta(name=job_name),
            spec=client.V1JobSpec(
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels={"job-name": job_name}),
                    spec=client.V1PodSpec(
                        containers=[
                            client.V1Container(
                                name="k6",
                                image="grafana/k6",
                                command=["k6", "run", "/scripts/script.js"],
                                volume_mounts=[
                                    client.V1VolumeMount(
                                        name="script-volume",
                                        mount_path="/scripts"
                                    )
                                ]
                            )
                        ],
                        restart_policy="Never",
                        volumes=[
                            client.V1Volume(
                                name="script-volume",
                                config_map=client.V1ConfigMapVolumeSource(
                                    name=script_configmap_name
                                )
                            )
                        ]
                    )
                )
            )
        )

        batch_v1.create_namespaced_job(namespace="default", body=job)
        return {"message": f"Job {job_name} created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))