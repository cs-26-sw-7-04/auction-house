"""Deployers: start a won task on the winner's node."""
import datetime
import logging
import os
from pathlib import Path
from typing import Any

from auction_house import plugins
from auction_house.domain import Task

log = logging.getLogger(__name__)

BIDDER_LABEL = "auction/bidder"


@plugins.deployers.register("logging")
class LoggingDeployer:
    """Deploys nothing; remembers what it was asked to. For development and tests."""

    def __init__(self):
        self.deployed: list[tuple[str, str]] = []

    def deploy(self, task: Task, bidder_id: str) -> str:
        """Record the request and return a fake handle."""
        log.info("would run task %s for %s", task.task_id, bidder_id)
        self.deployed.append((str(task.task_id), bidder_id))
        return f"log-{task.task_id}"


class KubernetesDeployer:
    """One batch/v1 Job per task. With `pin_to_node` the Job is placed on the
    node labelled `auction/bidder=<bidder_id>`; a single-node cluster such as a
    local k3s has no such labels, so leave it off there."""

    def __init__(
        self, batch_api: Any, *, namespace: str = "auction", pin_to_node: bool = False,
        image_pull_policy: str = "IfNotPresent", api_url: str = "http://auction-house:7777",
        api_key_secret_prefix: str = "bidder-",
    ):
        self.batch_api = batch_api
        self.namespace = namespace
        self.pin_to_node = pin_to_node
        self.image_pull_policy = image_pull_policy
        self.api_url = api_url.rstrip("/")
        self.api_key_secret_prefix = api_key_secret_prefix

    def build_job(self, task: Task, bidder_id: str, now: datetime.datetime) -> dict[str, Any]:
        """The batch/v1 Job manifest for one task."""
        spec, res = task.spec, task.spec.resources
        limits: dict[str, str] = {"cpu": f"{res.cpu_millis}m", "memory": f"{res.memory_mb}Mi"}
        if res.gpu:
            limits["nvidia.com/gpu"] = "1"
        task_id = str(task.task_id)
        pod: dict[str, Any] = {
            "restartPolicy": "Never",
            "containers": [{
                "name": "task",
                "image": spec.image,
                "imagePullPolicy": self.image_pull_policy,
                "env": [
                    {"name": "TASK_ID", "value": task_id},
                    {"name": "JOB_URL", "value": f"{self.api_url}/assignments/{task_id}/input"},
                    {"name": "RESULT_ENDPOINT", "value": f"{self.api_url}/assignments/{task_id}/result"},
                    {
                        "name": "AUCTION_API_KEY",
                        "valueFrom": {
                            "secretKeyRef": {
                                "name": f"{self.api_key_secret_prefix}{bidder_id}",
                                "key": "AH_API_KEY",
                            },
                        },
                    },
                ],
                "resources": {"requests": limits, "limits": limits},
            }],
        }
        if self.pin_to_node:
            pod["nodeSelector"] = {BIDDER_LABEL: bidder_id}
        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": f"task-{task.task_id}",
                "labels": {"auction/task": str(task.task_id), BIDDER_LABEL: bidder_id},
            },
            "spec": {
                "backoffLimit": 0,
                "ttlSecondsAfterFinished": 3600,
                "activeDeadlineSeconds": max(1, int((spec.deadline - now).total_seconds())),
                "template": {"spec": {**pod, "serviceAccountName": "bidder-worker"}},
            },
        }

    def deploy(self, task: Task, bidder_id: str) -> str:
        """Create the Job for the task and return its name as the handle."""
        job = self.build_job(task, bidder_id, datetime.datetime.now(datetime.timezone.utc))
        self.batch_api.create_namespaced_job(namespace=self.namespace, body=job)
        return job["metadata"]["name"]


@plugins.deployers.register("kubernetes")
def kubernetes_deployer(
    kubeconfig: str | None = None, namespace: str = "auction", pin_to_node: bool = False,
    image_pull_policy: str = "IfNotPresent", api_url: str = "http://auction-house:7777",
    api_key_secret_prefix: str = "bidder-",
) -> KubernetesDeployer:
    """Uses `kubeconfig`, else `$KUBECONFIG`, else `~/.kube/config` if present
    (local k3s), else the in-cluster service account."""
    from kubernetes import client, config  # optional: install the `k8s` extra

    path = kubeconfig or os.environ.get("KUBECONFIG") or str(Path.home() / ".kube" / "config")
    if Path(path).exists():
        api = client.BatchV1Api(config.new_client_from_config(path))
    else:
        config.load_incluster_config()
        api = client.BatchV1Api()
    return KubernetesDeployer(
        api, namespace=namespace, pin_to_node=pin_to_node, image_pull_policy=image_pull_policy,
        api_url=api_url, api_key_secret_prefix=api_key_secret_prefix,
    )
