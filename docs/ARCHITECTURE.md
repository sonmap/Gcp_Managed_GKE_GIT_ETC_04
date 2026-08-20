# Architecture

## 요청/생성 흐름

```text
[1] 사용자
    데이터 모델 작업 신청
        |
        v
[2] Java Portal
    승인 후 JSON 전송
        |
        v
[3] Cloud Run Adapter
    JSON -> Terraform inputValues 변환
        |
        +--> foundation-analysis 확인
        |       |
        |       +-- 없으면 Infrastructure Manager 생성
        |       |       |
        |       |       v
        |       |   GitHub foundation/
        |       |       |
        |       |       v
        |       |   Cloud Build (IM managed)
        |       |       |
        |       |       v
        |       |   Terraform apply
        |       |       |
        |       |       v
        |       |   GKE Autopilot
        |       |
        |       +-- ACTIVE면 재사용
        |
        v
[4] 과제 Deployment (예: model-001)
        |
        v
    GitHub task-blueprint/
        |
        v
    Cloud Build (IM managed)
        |
        v
    Terraform apply
        |
        +-- BigQuery Dataset
        +-- Google Service Account(GSA)
        +-- Namespace
        +-- ResourceQuota
        +-- Kubernetes Service Account(KSA)
        +-- Workload Identity
        +-- Jupyter Secret
        +-- Jupyter PVC
        +-- Jupyter Deployment
        +-- Jupyter Service
```

## 과제별 격리

```text
GKE Autopilot: analysis-autopilot-a
|
+-- namespace model-001
|   +-- Jupyter Pod
|   +-- KSA ksa-model-001
|   +-- PVC jupyter-workspace
|   +-- Service jupyter
|   +-- ResourceQuota
|
+-- namespace model-002
|   +-- Jupyter Pod
|   +-- KSA ksa-model-002
|   +-- PVC
|   +-- ResourceQuota
|
+-- ...

GCP IAM/Data
|
+-- model-001 GSA -> ds_model_001 only
+-- model-002 GSA -> ds_model_002 only
```

## 사용자와 Service Account

사람 계정은 Terraform이 새로 만들지 않습니다. 사내 IdP/Cloud Identity/Google Workspace에서 생성된 사용자 이메일을 `requestUser`로 받아 Dataset 권한을 부여합니다.

과제별 Service Account는 Terraform이 만듭니다.

```text
Jupyter Pod
   |
   v
KSA ksa-model-001
   |
   | Workload Identity
   v
GSA dm-task-model-001@...
   |
   +-- BigQuery Job User
   +-- ds_model_001 Data Editor
```

Service Account JSON Key는 생성/배포하지 않습니다.

## Jupyter

기본 Service는 `ClusterIP`입니다. 사용자 브라우저 접근은 Portal/Ingress/IAP/OAuth Proxy와 같은 인증된 공통 진입점을 별도로 두는 것이 권장됩니다. `LoadBalancer`도 변수로 선택 가능하지만 과제마다 외부 LB를 만드는 방식은 비용/보안 측면에서 기본값으로 권장하지 않습니다.

## 생명주기

생성:

```text
승인 -> IM Deployment create -> Terraform apply -> ACTIVE
```

변경:

```text
과제 사양 변경 -> 같은 Deployment update -> Terraform plan/apply
```

종료:

```text
IM Deployment delete --delete-policy=delete
   -> Terraform destroy
   -> Jupyter/Namespace/GSA/IAM/PVC/Dataset 삭제
```

운영에서는 Dataset/PVC를 즉시 삭제할지 Archive 후 삭제할지 별도 보존 정책을 두어야 합니다.
