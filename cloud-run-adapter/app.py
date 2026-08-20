import os
import re
import time
import uuid
from typing import Any, Dict

from flask import Flask, jsonify, request
import google.auth
from google.auth.transport.requests import AuthorizedSession

app = Flask(__name__)

API_ROOT = "https://config.googleapis.com/v1"
IM_PROJECT_ID = os.environ["IM_PROJECT_ID"]
IM_LOCATION = os.getenv("IM_LOCATION", "asia-northeast3")
IM_SERVICE_ACCOUNT = os.environ["IM_SERVICE_ACCOUNT"]
TF_REPO_URL = os.getenv(
    "TF_REPO_URL",
    "https://github.com/sonmap/Gcp_Managed_GKE_GIT_ETC_04.git",
)
TF_REPO_REF = os.getenv("TF_REPO_REF", "main")
TASK_TF_DIRECTORY = os.getenv("TF_DIRECTORY", "infra-manager/terraform/task-blueprint")
FOUNDATION_TF_DIRECTORY = os.getenv(
    "FOUNDATION_TF_DIRECTORY", "infra-manager/terraform/foundation"
)
FOUNDATION_DEPLOYMENT_ID = os.getenv("FOUNDATION_DEPLOYMENT_ID", "foundation-analysis")
DEFAULT_TARGET_PROJECT_ID = os.getenv("DEFAULT_TARGET_PROJECT_ID", "")

GKE_PROJECT_ID = os.getenv("GKE_PROJECT_ID", IM_PROJECT_ID)
GKE_LOCATION = os.getenv("GKE_LOCATION", IM_LOCATION)
GKE_CLUSTER_NAME = os.getenv("GKE_CLUSTER_NAME", "analysis-autopilot-a")
GKE_NETWORK_NAME = os.getenv("GKE_NETWORK_NAME", "managed02-dev-vpc")
GKE_SUBNETWORK_NAME = os.getenv("GKE_SUBNETWORK_NAME", "managed02-dev-subnet")
GKE_RELEASE_CHANNEL = os.getenv("GKE_RELEASE_CHANNEL", "REGULAR")
AUTO_CREATE_FOUNDATION = os.getenv("AUTO_CREATE_FOUNDATION", "true").lower() == "true"
FOUNDATION_WAIT_SECONDS = int(os.getenv("FOUNDATION_WAIT_SECONDS", "780"))
FOUNDATION_POLL_SECONDS = int(os.getenv("FOUNDATION_POLL_SECONDS", "10"))

credentials, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
authed = AuthorizedSession(credentials)


def _first(payload: Dict[str, Any], *names: str, default=None):
    for name in names:
        value = payload.get(name)
        if value is not None and str(value).strip() != "":
            return value
    return default


def _safe_id(value: str, prefix: str = "task") -> str:
    value = str(value).lower().strip()
    value = re.sub(r"[^a-z0-9-]", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    if not value:
        value = f"{prefix}-{uuid.uuid4().hex[:8]}"
    if not value[0].isalpha():
        value = f"{prefix}-{value}"
    return value[:60].rstrip("-")


def _dataset_id(task_id: str) -> str:
    raw = re.sub(r"[^A-Za-z0-9_]", "_", task_id)
    raw = re.sub(r"_+", "_", raw).strip("_")
    if not raw:
        raw = uuid.uuid4().hex[:8]
    return f"ds_{raw}"[:1024]


def _parent() -> str:
    return f"projects/{IM_PROJECT_ID}/locations/{IM_LOCATION}"


def _deployment_name(deployment_id: str) -> str:
    return f"{_parent()}/deployments/{deployment_id}"


def _deployment_url(deployment_id: str) -> str:
    return f"{API_ROOT}/{_deployment_name(deployment_id)}"


def _json_or_text(response):
    try:
        return response.json()
    except Exception:
        return {"raw": response.text}


def _map_portal_json(payload: Dict[str, Any]) -> Dict[str, str]:
    task_id = str(
        _first(payload, "taskId", "task_id", "projectId", "project_id", "requestId")
        or ""
    )
    if not task_id:
        raise ValueError("taskId is required")

    target_project_id = str(
        _first(
            payload,
            "targetProjectId",
            "target_project_id",
            "gcpProjectId",
            "gcp_project_id",
            default=DEFAULT_TARGET_PROJECT_ID,
        )
        or ""
    )
    if not target_project_id:
        raise ValueError(
            "targetProjectId is required, or set DEFAULT_TARGET_PROJECT_ID on Cloud Run"
        )

    location = str(_first(payload, "location", "region", default=IM_LOCATION))

    mapped = {
        "task_id": task_id,
        "task_name": str(
            _first(payload, "taskName", "task_name", "projectName", default=task_id)
        ),
        "group": str(_first(payload, "group", "groupCode", "group_code", default="analysis")).lower(),
        "request_user": str(
            _first(payload, "requestUser", "request_user", "userEmail", "user_email", default="")
        ),
        "target_project_id": target_project_id,
        "dataset_id": _dataset_id(task_id),
        "bq_location": location,
        "bigquery_role": str(
            _first(payload, "bigqueryRole", "bigquery_role", default="editor")
        ).lower(),
        "gke_project_id": GKE_PROJECT_ID,
        "gke_cluster_name": GKE_CLUSTER_NAME,
        "gke_location": GKE_LOCATION,
        "jupyter_image": str(
            _first(
                payload,
                "jupyterImage",
                "jupyter_image",
                default="quay.io/jupyter/base-notebook:latest",
            )
        ),
        "jupyter_cpu_request": str(
            _first(payload, "cpuRequest", "cpu_request", default="2")
        ),
        "jupyter_cpu_limit": str(
            _first(payload, "cpuLimit", "cpu_limit", default="4")
        ),
        "jupyter_memory_request": str(
            _first(payload, "memoryRequest", "memory_request", default="8Gi")
        ),
        "jupyter_memory_limit": str(
            _first(payload, "memoryLimit", "memory_limit", default="16Gi")
        ),
        "storage_size": str(_first(payload, "storage", "storageSize", default="50Gi")),
        "jupyter_service_type": str(
            _first(payload, "jupyterServiceType", "jupyter_service_type", default="ClusterIP")
        ),
        "expire_date": str(_first(payload, "expireDate", "expire_date", default="")),
    }

    if mapped["bigquery_role"] not in {"viewer", "editor", "owner"}:
        raise ValueError("bigqueryRole must be viewer, editor, or owner")
    if mapped["jupyter_service_type"] not in {"ClusterIP", "LoadBalancer"}:
        raise ValueError("jupyterServiceType must be ClusterIP or LoadBalancer")

    return mapped


def _foundation_inputs() -> Dict[str, str]:
    return {
        "project_id": GKE_PROJECT_ID,
        "region": GKE_LOCATION,
        "network_name": GKE_NETWORK_NAME,
        "subnetwork_name": GKE_SUBNETWORK_NAME,
        "cluster_name": GKE_CLUSTER_NAME,
        "release_channel": GKE_RELEASE_CHANNEL,
    }


def _blueprint_body(
    directory: str,
    inputs: Dict[str, str],
    annotations: Dict[str, str],
    deployment_name: str | None = None,
):
    body = {
        "serviceAccount": IM_SERVICE_ACCOUNT,
        "terraformBlueprint": {
            "gitSource": {
                "repo": TF_REPO_URL,
                "directory": directory,
                "ref": TF_REPO_REF,
            },
            "inputValues": {
                key: {"inputValue": str(value)} for key, value in inputs.items()
            },
        },
        "annotations": annotations,
    }
    if deployment_name:
        body["name"] = deployment_name
    return body


def _create_deployment(
    deployment_id: str,
    directory: str,
    inputs: Dict[str, str],
    annotations: Dict[str, str],
):
    response = authed.post(
        f"{API_ROOT}/{_parent()}/deployments",
        params={"deploymentId": deployment_id, "requestId": str(uuid.uuid4())},
        json=_blueprint_body(directory, inputs, annotations),
        timeout=60,
    )
    return response, _json_or_text(response)


def _update_deployment(
    deployment_id: str,
    directory: str,
    inputs: Dict[str, str],
    annotations: Dict[str, str],
):
    name = _deployment_name(deployment_id)
    response = authed.patch(
        _deployment_url(deployment_id),
        params={
            "updateMask": "terraformBlueprint,serviceAccount,annotations",
            "requestId": str(uuid.uuid4()),
        },
        json=_blueprint_body(directory, inputs, annotations, name),
        timeout=60,
    )
    return response, _json_or_text(response)


def _ensure_foundation() -> Dict[str, Any]:
    existing = authed.get(_deployment_url(FOUNDATION_DEPLOYMENT_ID), timeout=30)

    if existing.status_code == 404:
        if not AUTO_CREATE_FOUNDATION:
            raise RuntimeError("foundation-analysis does not exist and AUTO_CREATE_FOUNDATION=false")
        response, result = _create_deployment(
            FOUNDATION_DEPLOYMENT_ID,
            FOUNDATION_TF_DIRECTORY,
            _foundation_inputs(),
            {"source": "data-model-portal", "layer": "foundation"},
        )
        if not response.ok:
            raise RuntimeError(
                f"failed to create foundation deployment: {response.status_code} {result}"
            )
    elif not existing.ok:
        raise RuntimeError(
            f"failed to inspect foundation deployment: {existing.status_code} {existing.text}"
        )
    else:
        current = existing.json()
        state = current.get("state", "")
        if state == "ACTIVE":
            return current
        if state == "FAILED":
            response, result = _update_deployment(
                FOUNDATION_DEPLOYMENT_ID,
                FOUNDATION_TF_DIRECTORY,
                _foundation_inputs(),
                {"source": "data-model-portal", "layer": "foundation"},
            )
            if not response.ok:
                raise RuntimeError(
                    f"failed to retry foundation deployment: {response.status_code} {result}"
                )
        elif state == "DELETING":
            raise RuntimeError("foundation deployment is deleting")

    deadline = time.monotonic() + FOUNDATION_WAIT_SECONDS
    last_state = "CREATING"

    while time.monotonic() < deadline:
        time.sleep(FOUNDATION_POLL_SECONDS)
        response = authed.get(_deployment_url(FOUNDATION_DEPLOYMENT_ID), timeout=30)
        if not response.ok:
            raise RuntimeError(
                f"failed while waiting for foundation: {response.status_code} {response.text}"
            )
        current = response.json()
        last_state = current.get("state", "UNKNOWN")
        if last_state == "ACTIVE":
            return current
        if last_state == "FAILED":
            raise RuntimeError(
                f"foundation deployment failed: {current.get('stateDetail', 'unknown error')}"
            )

    raise RuntimeError(
        f"foundation did not become ACTIVE within {FOUNDATION_WAIT_SECONDS}s; last state={last_state}"
    )


def _upsert_task(mapped: Dict[str, str]):
    deployment_id = _safe_id(mapped["task_id"], "model")
    annotations = {
        "source": "data-model-portal",
        "layer": "task",
        "task-id": deployment_id,
        "group": _safe_id(mapped["group"], "group")[:20],
    }

    existing = authed.get(_deployment_url(deployment_id), timeout=30)
    if existing.status_code == 404:
        return (*_create_deployment(deployment_id, TASK_TF_DIRECTORY, mapped, annotations), "create")
    if not existing.ok:
        return None, {
            "error": "failed to inspect task deployment",
            "status": existing.status_code,
            "detail": existing.text,
        }, "inspect-error"

    current = existing.json()
    if current.get("state") in {"CREATING", "UPDATING", "DELETING"}:
        return None, {
            "error": "task deployment is busy",
            "deployment": _deployment_name(deployment_id),
            "state": current.get("state"),
        }, "busy"

    return (*_update_deployment(deployment_id, TASK_TF_DIRECTORY, mapped, annotations), "update")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/deploy")
def deploy():
    payload = request.get_json(silent=False)
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON object required"}), 400

    try:
        mapped = _map_portal_json(payload)
        foundation = _ensure_foundation()
    except (ValueError, RuntimeError) as exc:
        code = 400 if isinstance(exc, ValueError) else 502
        return jsonify({"error": str(exc), "phase": "foundation-or-mapping"}), code

    response, result, action = _upsert_task(mapped)
    if response is None:
        code = 409 if action == "busy" else 502
        result["phase"] = "task"
        result["mappedVariables"] = mapped
        return jsonify(result), code

    if not response.ok:
        return jsonify(
            {
                "error": "Infrastructure Manager task request failed",
                "phase": "task",
                "action": action,
                "status": response.status_code,
                "detail": result,
                "mappedVariables": mapped,
            }
        ), 502

    return jsonify(
        {
            "action": action,
            "phase": "task",
            "foundation": {
                "deployment": _deployment_name(FOUNDATION_DEPLOYMENT_ID),
                "state": foundation.get("state", "ACTIVE"),
                "cluster": GKE_CLUSTER_NAME,
            },
            "deployment": _deployment_name(_safe_id(mapped["task_id"], "model")),
            "operation": result.get("name"),
            "mappedVariables": mapped,
            "infrastructureManagerResponse": result,
        }
    ), 202


@app.get("/status")
def status():
    operation = request.args.get("operation", "").strip()
    if not operation:
        return jsonify({"error": "operation query parameter is required"}), 400
    operation = operation.removeprefix("https://config.googleapis.com/v1/").lstrip("/")
    if "/operations/" not in operation:
        return jsonify({"error": "invalid Infrastructure Manager operation name"}), 400
    response = authed.get(f"{API_ROOT}/{operation}", timeout=30)
    return jsonify(_json_or_text(response)), response.status_code


@app.get("/deployments/<deployment_id>")
def deployment_status(deployment_id: str):
    deployment_id = _safe_id(deployment_id, "model")
    response = authed.get(_deployment_url(deployment_id), timeout=30)
    return jsonify(_json_or_text(response)), response.status_code


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
