# Portal API Contract

기존 Java Portal은 Terraform 파일을 전달하지 않습니다. 승인된 업무 JSON만 Cloud Run Adapter `/deploy`로 전송합니다.

## POST /deploy

예제:

```json
{
  "taskId": "model-001",
  "taskName": "fraud-detection-model",
  "requestUser": "user01@example.com",
  "group": "fraud",
  "targetProjectId": "dev-com-334508",
  "location": "asia-northeast3",
  "cpuRequest": "2",
  "cpuLimit": "4",
  "memoryRequest": "8Gi",
  "memoryLimit": "16Gi",
  "storage": "50Gi",
  "bigqueryRole": "editor",
  "jupyterImage": "quay.io/jupyter/base-notebook:latest",
  "jupyterServiceType": "ClusterIP",
  "expireDate": "2026-12-31"
}
```

Cloud Run Adapter가 내부적으로 다음 Terraform 변수로 변환합니다.

```text
task_id                 = model-001
task_name               = fraud-detection-model
request_user            = user01@example.com
group                   = fraud
target_project_id       = dev-com-334508
dataset_id              = ds_model_001
bigquery_role           = editor
gke_cluster_name        = analysis-autopilot-a
jupyter_cpu_request     = 2
jupyter_cpu_limit       = 4
jupyter_memory_request  = 8Gi
jupyter_memory_limit    = 16Gi
storage_size            = 50Gi
jupyter_image           = quay.io/jupyter/base-notebook:latest
jupyter_service_type    = ClusterIP
expire_date             = 2026-12-31
```

## 상태 조회

Infrastructure Manager Operation 이름이 반환되면:

```text
GET /status?operation=projects/.../locations/.../operations/...
```

Deployment 자체를 조회하려면:

```text
GET /deployments/model-001
```

## Foundation

`/deploy` 요청 시 `foundation-analysis`가 `ACTIVE`인지 먼저 확인합니다. 없으면 `infra-manager/terraform/foundation`을 사용해 자동 생성합니다. 운영에서는 Foundation을 플랫폼 구축 단계에 미리 생성해 두면 매 과제 요청은 Task Blueprint만 실행하므로 응답 시간이 짧아집니다.

## 보안

PoC deploy script는 `--allow-unauthenticated`를 사용합니다. 운영에서는 Cloud Run 인증을 활성화하고 Java Web 서버가 OIDC/서비스 계정 기반으로 호출하거나 내부 승인 경로를 사용해야 합니다.
