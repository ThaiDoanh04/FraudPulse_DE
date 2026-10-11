# Architecture Decision Records (ADR)

Mỗi ADR ghi lại một quyết định quan trọng: bối cảnh, lựa chọn đã chốt, các phương án bị loại và lý do, cùng hệ quả. ADR không bao giờ bị xoá; khi một quyết định thay đổi, ta viết ADR mới thay thế ADR cũ.

| ADR | Quyết định | Trạng thái |
|---|---|---|
| [ADR-001](ADR-001-kafka-cdc-event-backbone.md) | Kafka kết hợp Debezium CDC làm xương sống sự kiện | Đã chấp nhận |
| [ADR-002](ADR-002-iceberg-lakehouse-dbt-trino.md) | Lakehouse Iceberg với Spark, dbt và Trino | Đã chấp nhận |
| [ADR-003](ADR-003-feast-feature-store.md) | Feast làm feature store | Đã chấp nhận |
| [ADR-004](ADR-004-flink-sql-velocity-features.md) | Flink SQL cho velocity feature streaming | Đã chấp nhận |
| [ADR-005](ADR-005-lightgbm-model-and-evaluation.md) | LightGBM kèm rules dự phòng; PR-AUC, recall tại FPR cố định, chi phí | Đã chấp nhận |
| [ADR-006](ADR-006-scoring-service-and-model-registry.md) | Scoring FastAPI + ONNX với champion/challenger trên MLflow | Đã chấp nhận |
| [ADR-007](ADR-007-portfolio-scale-governance.md) | Governance ở quy mô portfolio | Đã chấp nhận |

## Mẫu ADR

ADR mới dùng số tiếp theo và các mục sau, đúng thứ tự (được kiểm tra bởi `tests/test_docs.py`):

```markdown
# ADR-NNN: Tiêu đề

## Trạng thái
Đề xuất | Đã chấp nhận | Bị thay thế bởi ADR-XXX | Ngừng sử dụng

## Ngày
YYYY-MM-DD

## Bối cảnh
## Quyết định
## Các phương án đã cân nhắc
### Phương án A   (ít nhất hai phương án)
## Hệ quả
```
