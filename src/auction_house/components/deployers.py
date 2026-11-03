"""Deployers: start a won task on the winner's node."""
import datetime
import logging
import os
from pathlib import Path
from typing import Any

from auction_house import plugins
from auction_house.domain import Award, Task

log = logging.getLogger(__name__)

BIDDER_LABEL = "auction/bidder"


@plugins.deployers.register("log")
class LoggingDeployer:
    """Deploys nothing; remembers what it was asked to. For development and tests."""

    def __init__(self):
        self.deployed: list[tuple[str, str]] = []

    def deploy(self, task: Task, award: Award) -> str:
        """:3"""
        log.info("would run task %s for %s", task.task_id, award.bidder_id)
        self.deployed.append((str(task.task_id), award.bidder_id))
        return f"log-{task.task_id}"


class KubernetesDeployer:
    """One batch/v1 Job per task. With `pin_to_node` the Job is placed on the
    node labelled `auction/bidder=<bidder_id>`; a single-node cluster such as a
    local k3s has no such labels, so leave it off there."""

    def __init__(
        self, batch_api: Any, *, namespace: str = "auction", pin_to_node: bool = False,
        image_pull_policy: str = "IfNotPresent",
    ):
        self.batch_api = batch_api
        self.namespace = namespace
        self.pin_to_node = pin_to_node
        self.image_pull_policy = image_pull_policy

    def build_job(self, task: Task, award: Award, now: datetime.datetime) -> dict[str, Any]:
        """:3"""
        spec, res = task.spec, task.spec.resources
        limits: dict[str, str] = {"cpu": f"{res.cpu_millis}m", "memory": f"{res.memory_mb}Mi"}
        if res.gpu:
            limits["nvidia.com/gpu"] = "1"
        pod: dict[str, Any] = {
            "restartPolicy": "Never",
            "containers": [{
                "name": "task",
                "image": spec.image,
                "imagePullPolicy": self.image_pull_policy,
                "env": [{"name": "TASK_ID", "value": str(task.task_id)}],
                "resources": {"requests": limits, "limits": limits},
            }],
        }
        if self.pin_to_node:
            pod["nodeSelector"] = {BIDDER_LABEL: award.bidder_id}
        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": f"task-{task.task_id}",
                "labels": {"auction/task": str(task.task_id), BIDDER_LABEL: award.bidder_id},
            },
            "spec": {
                "backoffLimit": 0,
                "ttlSecondsAfterFinished": 3600,
                "activeDeadlineSeconds": max(1, int((spec.deadline - now).total_seconds())),
                "template": {"spec": pod},
            },
        }

    def deploy(self, task: Task, award: Award) -> str:
        """:3"""
        job = self.build_job(task, award, datetime.datetime.now(datetime.timezone.utc))
        self.batch_api.create_namespaced_job(namespace=self.namespace, body=job)
        return job["metadata"]["name"]


@plugins.deployers.register("kubernetes")
def kubernetes_deployer(
    kubeconfig: str | None = None, namespace: str = "auction", pin_to_node: bool = False,
    image_pull_policy: str = "IfNotPresent",
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
    )
