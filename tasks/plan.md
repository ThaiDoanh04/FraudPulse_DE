# Implementation Plan: Real-time Fraud Detection Platform (dự án portfolio)

## Overview

Dự án cá nhân để đưa vào CV: một nền tảng phát hiện gian lận chạy trọn vẹn trên một máy (docker-compose, phần cuối lên Kubernetes local bằng kind), đi qua đủ 9 tầng:

ingestion → ETL/ELT → feature engineering → training → model registry → real-time inference → monitoring → CI/CD → governance

Mục tiêu không phải quy mô ngân hàng, mà là **mỗi tầng có một phần chạy thật, đo được, và giải thích được trong phỏng vấn**. Ước lượng: 10–12 tuần, khoảng 10–15 giờ/tuần.

## Scope: giữ gì, thu gọn gì

| Tầng | Bản ngân hàng | Bản portfolio |
|---|---|---|
| Nguồn dữ liệu | Core banking | Postgres đóng vai core banking + script replay giao dịch theo đúng nhịp thời gian từ dataset công khai |
| Ingestion | Kafka cluster + Debezium | Kafka 1 broker (KRaft) + Debezium + Schema Registry |
| Lakehouse | Iceberg trên object storage, Spark, dbt, Trino | Giữ nguyên, chạy local: MinIO + Iceberg REST catalog + Spark + dbt-trino + Trino |
| Orchestration | Airflow HA | Airflow 1 node |
| Feature store | Feast + Redis cluster | Feast + Redis 1 node |
| Streaming | Flink cluster | Flink 1 JobManager + 1 TaskManager, viết bằng Flink SQL |
| Training / registry | LightGBM + MLflow | Giữ nguyên |
| Serving | KServe trên K8s | FastAPI + ONNX Runtime trong Docker; Phase 4 deploy lên kind bằng Helm |
| Monitoring | Prometheus, Grafana, Evidently | Giữ nguyên |
| CI/CD | GitLab CI + ArgoCD | GitHub Actions + ArgoCD trên kind (repo public để nhà tuyển dụng xem được) |
| Governance | OpenMetadata, Ranger, Vault, GE | Great Expectations + hash PII tại ingestion + OpenMetadata (chạy riêng khi demo) + phân quyền file-based của Trino + audit trail. Bỏ Ranger và Vault (quá nặng, ghi lý do trong ADR) |

## Dataset

**Credit Card Transactions Fraud Detection Dataset (Sparkov, Kaggle)**: ~1,8 triệu giao dịch có timestamp, số thẻ, merchant, số tiền, toạ độ khách và merchant, nhãn `is_fraud`. Phù hợp vì có timestamp thật để replay theo thời gian và tính velocity features, có toạ độ để làm feature khoảng cách.

Phương án dự phòng: PaySim (chuyển tiền di động) hoặc IEEE-CIS (nhiều feature nhưng ẩn danh, khó giải thích).

## Yêu cầu máy

- RAM 16 GB (tối thiểu), 32 GB thì thoải mái; ~40 GB ổ trống.
- Docker Compose dùng **profiles** để không bật mọi thứ cùng lúc: `core` (Postgres, Kafka, MinIO, Trino), `streaming` (Debezium, Flink, Redis), `ml` (MLflow, Airflow), `obs` (Prometheus, Grafana), `gov` (OpenMetadata).

## Architecture Decisions

Ghi trong `docs/decisions/` (Task 0.1), mỗi ADR ngắn gọn ~1 trang. Đây cũng là tài liệu giúp trả lời câu "tại sao chọn X" khi phỏng vấn.

- ADR-001: Kafka làm xương sống sự kiện, CDC bằng Debezium từ Postgres
- ADR-002: Lakehouse Iceberg + dbt-trino, mô hình medallion
- ADR-003: Feast làm feature store, point-in-time join chống rò rỉ
- ADR-004: Flink SQL cho velocity features
- ADR-005: LightGBM + rules fallback; đánh giá bằng PR-AUC, recall@FPR, cost
- ADR-006: Scoring service FastAPI + ONNX, MLflow alias champion/challenger
- ADR-007: Governance mức portfolio: những gì giữ, những gì bỏ và vì sao

## Dependency Graph

```
Task 0.1–0.3 (repo, compose, dataset, ADR)
        │
Phase 1 walking skeleton:
  replay → Postgres → Debezium → Kafka → Iceberg bronze → dbt silver
                                                    └→ 1 feature (Feast) → model baseline (MLflow) → /score
        │
Phase 2 batch ML:  DQ + Airflow → gold features → Feast → training pipeline → champion
        │
Phase 3 real-time: Flink velocity → Redis → /score dùng feature real-time → skew check → load test
        │
Phase 4 MLOps:     metrics + prediction log → drift → CI → CT → Helm/kind/ArgoCD
        │
Phase 5:           governance (lineage, phân quyền, audit) → README, demo, kết quả
```

## Task List

Chi tiết: `tasks/todo.md`.

### Phase 0: Nền móng (tuần 1)
- [x] Task 0.1: SPEC ngắn + 7 ADR
- [ ] Task 0.2: Repo + docker-compose profiles + CI lint/test
- [ ] Task 0.3: Dataset + chia tập theo thời gian

### Checkpoint 0
- [ ] `make up-core` chạy; CI xanh; dataset nằm trong Postgres

### Phase 1: Walking skeleton (tuần 2–3)
- [ ] Task 1.1: Replay giao dịch → Postgres → Debezium → Kafka (có hash PII)
- [ ] Task 1.2: Kafka → Iceberg bronze + dbt silver
- [ ] Task 1.3: Một feature trong Feast → model baseline → MLflow
- [ ] Task 1.4: Scoring service `/score` tối thiểu

### Checkpoint 1
- [ ] Một giao dịch đi hết vòng từ Postgres tới score; quay GIF demo đầu tiên

### Phase 2: Batch ML đúng chuẩn (tuần 4–5)
- [ ] Task 2.1: Data quality + Airflow DAG
- [ ] Task 2.2: Gold features (khách hàng, merchant, khoảng cách) + Feast
- [ ] Task 2.3: Training pipeline + báo cáo đánh giá + model card

### Checkpoint 2
- [ ] Model v1 có bảng kết quả so với baseline và rule đơn giản

### Phase 3: Real-time (tuần 6–7)
- [ ] Task 3.1: Flink SQL velocity features → Redis
- [ ] Task 3.2: `/score` dùng feature real-time + rules fallback
- [ ] Task 3.3: Kiểm tra train/serve skew
- [ ] Task 3.4: Load test + chaos test

### Checkpoint 3
- [ ] Có số p99 latency và throughput để ghi vào CV

### Phase 4: MLOps (tuần 8–10)
- [ ] Task 4.1: Prometheus + Grafana + log dự đoán vào Iceberg
- [ ] Task 4.2: Drift monitoring với kịch bản drift giả lập
- [ ] Task 4.3: CI: test + build image + push GHCR
- [ ] Task 4.4: CT: retrain → validation gates → challenger → promote
- [ ] Task 4.5: Helm + kind + ArgoCD (GitOps)

### Checkpoint 4
- [ ] Đổi model bằng một MR, ArgoCD tự deploy

### Phase 5: Governance + showcase (tuần 11–12)
- [ ] Task 5.1: Lineage (OpenMetadata) + phân quyền Trino + audit trail
- [ ] Task 5.2: README, sơ đồ, demo, bảng kết quả, gợi ý dòng CV

### Checkpoint cuối
- [ ] Người lạ clone repo, chạy `make demo`, thấy toàn bộ hệ thống trong < 15 phút

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Máy không đủ RAM khi bật cả stack | High | Compose profiles; giới hạn memory từng service; Flink và OpenMetadata chỉ bật khi cần |
| Mắc kẹt cấu hình (Iceberg catalog, Feast offline store với Trino) | High | Walking skeleton ở Phase 1 để gặp lỗi tích hợp sớm; nếu Feast–Trino quá khó thì dùng Feast file offline store (Parquet export từ dbt) và ghi lại trong ADR |
| Ôm đồm, không xong | High | Mỗi phase kết thúc bằng thứ demo được; Task 4.5 và OpenMetadata là phần có thể lùi nếu trễ |
| Kết quả model "đẹp giả" do rò rỉ dữ liệu | Med | Split theo thời gian, point-in-time join, test rò rỉ |
| Flink khó debug | Med | Dùng Flink SQL thay vì PyFlink DataStream; test trên lượng dữ liệu nhỏ trước |

## Open Questions

1. Máy của bạn có bao nhiêu RAM? (quyết định chạy đủ stack cùng lúc hay phải tách)
2. ~~Ngôn ngữ README/ADR?~~ Đã chốt: tiếng Việt.
3. Có sẵn tài khoản GitHub để repo public và dùng GitHub Actions/GHCR không?
