# GCP Managed Data Model Workspace (GKE Autopilot)

데이터 모델 작업 신청/승인 후 별도 VM을 생성하던 구조를 GKE Autopilot 기반의 공통 분석 플랫폼으로 전환하는 PoC/Reference 구현입니다.

## 목표 구조

```text
사용자 포털(Java Web)
        |
        | 승인된 JSON
        v
Cloud Run Adapter
        |
        | Infrastructure Manager REST API
        v
Infrastructure Manager
        |
        | GitHub Terraform Blueprint
        v
Cloud Build (Infrastructure Manager managed execution)
        |
        +--> foundation Terraform (공통 1회)
        |      +-- GKE Autopilot
        |
        +--> task Terraform (데이터 모델 과제마다)
               +-- Namespace
               +-- ResourceQuota
               +-- BigQuery Dataset
               +-- Google Service Account(GSA)
               +-- Kubernetes Service Account(KSA)
               +-- Workload Identity (KSA -> GSA)
               +-- 사용자 BigQuery IAM
               +-- Jupyter Notebook Deployment
               +-- PVC
               +-- Service
```

## AS-IS / TO-BE

AS-IS: 과제 승인 -> 신규 GCP Project -> VM -> Jupyter 설치 -> BigQuery -> 사용자/SA/IAM

TO-BE: 공통 GKE Autopilot Foundation을 재사용하고, 신규 과제마다 Namespace + Dataset + GSA/KSA + Workload Identity + Jupyter Workspace를 생성합니다.

과제마다 GKE Cluster를 새로 만들지 않습니다. 보안/조직 정책상 프로젝트 단위 격리가 필요한 경우에는 `targetProjectId`를 다르게 전달하거나 Foundation을 그룹/환경별로 분리할 수 있습니다.

## 디렉터리

```text
infra-manager/terraform/bootstrap/       최초 1회 IAM/SA 준비(관리자 실행)
infra-manager/terraform/foundation/      공통 GKE Autopilot Foundation
infra-manager/terraform/task-blueprint/  과제별 Workspace 자원
cloud-run-adapter/                       포털 JSON -> IM/Terraform 변수 변환
portal-integration/                      기존 Java Web 연동 예제
jupyter-image/                           공통 Jupyter 이미지/패키지/Cloud Build
examples/                                요청 JSON 예제
docs/                                    구조/운영 설명
```

## 사용자 계정 정책

사람 계정은 Cloud Identity/Google Workspace/사내 IdP에서 수명주기를 관리하는 것을 권장합니다. 이 Blueprint는 신규 사람 계정을 직접 생성하지 않고 `requestUser`로 전달된 기존 회사 계정에 과제 Dataset IAM을 부여합니다.

Service Account는 과제마다 생성합니다. Jupyter Pod에는 JSON Key를 넣지 않고 KSA -> GSA Workload Identity를 사용합니다.

실제 사람 계정까지 자동 생성해야 한다면 Google Workspace/Cloud Identity Admin API를 별도 Identity Provisioning 단계로 추가해야 합니다. 인프라 과제 Terraform과 사람 계정 수명주기를 한 State에 결합하는 것은 권장하지 않습니다.

## 요청 예시

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

## Foundation vs Task

- `foundation-analysis`: 공통 GKE Autopilot을 소유하는 Infrastructure Manager Deployment. 기본적으로 1개만 존재합니다.
- `model-001`, `model-002`, ...: 과제별 Infrastructure Manager Deployment. 각 Deployment는 독립 Terraform State/Revision을 가집니다.

## Jupyter 이미지

`jupyter-image/`에는 공통 Notebook 이미지 소스와 패키지 목록, Cloud Build 설정이 있습니다. 운영에서는 Artifact Registry에 빌드한 고정 tag/digest 이미지를 `jupyterImage`로 전달하는 것을 권장합니다.

## Jupyter 접근

기본 Service Type은 `ClusterIP`입니다. 외부 LoadBalancer 비용과 무인증 노출을 피하기 위한 기본값입니다. 실제 사용자 접속은 사내 Portal/Ingress/IAP/OAuth Proxy 등 승인된 접근 계층을 통해 연결하는 것을 권장합니다.

## Bootstrap

Infrastructure Manager 실행 Service Account가 GKE, BigQuery, IAM, Service Account를 생성할 권한은 최초 1회 플랫폼 관리자가 부여해야 합니다. `infra-manager/terraform/bootstrap`은 그 초기 권한을 코드화하기 위한 예제입니다. 권한 없는 Service Account가 스스로 권한을 올릴 수는 없습니다.

## 주의

- PoC 기본값은 단일 프로젝트를 기준으로 합니다.
- 운영에서는 Git `main` 대신 release tag 또는 commit SHA 고정을 권장합니다.
- Jupyter 이미지도 운영에서는 `latest` 대신 고정 tag/digest를 사용하십시오.
- 과제 종료 시 BigQuery Dataset/PVC 삭제 정책은 데이터 보존 정책에 맞게 별도로 결정해야 합니다.
