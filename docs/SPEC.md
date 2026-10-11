# SPEC: Nền tảng phát hiện gian lận thời gian thực

Trạng thái: Đã chấp nhận · Cập nhật: 2026-10-11

## Bài toán

Gian lận thẻ phải được phát hiện ngay khi giao dịch đang được cấp phép, chứ không phải trong báo cáo batch ngày hôm sau. Muốn vậy cần hai thứ hoạt động cùng nhau: feature phản ánh những gì vừa xảy ra vài giây trước (ví dụ "thẻ này đã có 5 giao dịch trong 10 phút qua"), và một model chấm điểm từng giao dịch trong ngân sách độ trễ chặt.

Dự án xây dựng một nền tảng end-to-end làm việc này trên một máy, đi qua đủ các tầng mà một hệ thống production cần: ingestion, ETL/ELT, feature engineering, training, model registry, real-time inference, monitoring, CI/CD và governance. Đây là dự án portfolio: mục tiêu là một hệ thống mà mỗi tầng đều chạy thật, đo được và có lý do lựa chọn được ghi lại.

## Phạm vi

Trong phạm vi:

- Một database Postgres đóng vai hệ thống core banking, được nạp bởi script replay chèn giao dịch lịch sử theo đúng nhịp thời gian gốc (có hệ số tăng tốc cấu hình được).
- Change data capture từ Postgres vào Kafka, rồi vào lakehouse Iceberg tổ chức theo bronze / silver / gold.
- Feature batch (dbt) và velocity feature streaming (Flink SQL), cả hai được phục vụ qua Feast để training và serving dùng chung một định nghĩa.
- Model LightGBM huấn luyện với cách chia dữ liệu theo thời gian, được theo dõi và quản lý phiên bản bằng MLflow, export sang ONNX.
- Scoring API trả về điểm, quyết định, reason codes, và chuyển sang rules khi một thành phần phụ thuộc bị lỗi.
- Monitoring vận hành và ML (độ trễ, drift, train/serve skew), CI, continuous training có validation gates, và triển khai scoring service theo GitOps lên cluster Kubernetes local.
- Governance phù hợp với dự án một người: hash PII tại ingestion, data quality gates, lineage, phân quyền theo vai trò trong Trino, và audit trail cho từng giao dịch.

## Dữ liệu

**Credit Card Transactions Fraud Detection Dataset** (Kaggle, `kartik2112/fraud-detection`), được mô phỏng bằng công cụ Sparkov.

Quy mô dự kiến (sẽ xác minh khi nạp dữ liệu ở Task 0.3):

- Hai file `fraudTrain.csv` (~1,3 triệu dòng) và `fraudTest.csv` (~0,56 triệu dòng), giai đoạn 2019-01-01 đến 2020-12-31.
- Khoảng 1.000 chủ thẻ và 800 merchant; tỷ lệ gian lận khoảng 0,5%.
- Các cột gồm thời gian giao dịch, số thẻ, merchant và category, số tiền, toạ độ chủ thẻ và merchant, ngày sinh, mã giao dịch (`trans_num`) và nhãn `is_fraud`.

Lý do chọn dataset này: có timestamp thật (cần cho replay và velocity feature), có mã định danh thẻ và merchant ổn định (cần cho tổng hợp theo từng thực thể), và có toạ độ (cho phép làm feature khoảng cách). Các phương án khác được ghi trong ADR-005.

Dữ liệu là mô phỏng, nhưng các trường của chủ thẻ (tên, địa chỉ, ngày sinh, số thẻ) được xử lý như PII thật; xem ADR-007.

### Chia dữ liệu theo thời gian

Dữ liệu được chia theo thời gian, không bao giờ chia ngẫu nhiên, để kết quả offline phản ánh đúng hiệu năng của model trên các giao dịch tương lai.

| Giai đoạn | Mục đích |
|---|---|
| 2019-01-01 đến 2020-04-30 | Training (nạp vào Postgres làm dữ liệu lịch sử) |
| 2020-05-01 đến 2020-06-21 | Validation và chọn ngưỡng |
| 2020-06-21 đến 2020-12-31 | Tập test giữ riêng, đồng thời là luồng được replay qua pipeline live |

Mốc chính xác được chốt ở Task 0.3 sau khi xác nhận khoảng thời gian của từng file.

## Chỉ số thành công

Chất lượng model, đo trên giai đoạn test giữ riêng:

| Chỉ số | Mục tiêu |
|---|---|
| PR-AUC | Cao hơn model baseline (Task 1.3) và cao hơn rule ngưỡng số tiền đơn giản |
| Recall@1%FPR | Báo cáo cho mọi phiên bản model; v2 (có velocity feature) phải vượt v1 |
| Tiết kiệm theo chi phí | Số tiền gian lận chặn được trừ chi phí review cố định cho mỗi false positive; báo cáo theo từng phiên bản |

Không đặt trước mục tiêu PR-AUC tuyệt đối. Trên dataset này, điểm cao bất thường (trên 0,95) được coi là tín hiệu cần kiểm tra rò rỉ dữ liệu, không phải thành công.

Serving và pipeline, đo trên máy local:

| Chỉ số | Mục tiêu |
|---|---|
| Độ trễ `/v1/score` | p99 < 50 ms |
| Thông lượng | ≥ 500 req/s duy trì liên tục không lỗi |
| Độ tươi velocity feature | p95 < 1 s từ thời điểm sự kiện tới Redis |
| Fallback | Scoring vẫn trả lời trong ngân sách độ trễ khi Redis hoặc model không khả dụng |
| Train/serve skew | ≥ 99% giá trị feature online đã log khớp với giá trị tính lại offline |

Khả năng tái lập:

| Chỉ số | Mục tiêu |
|---|---|
| Cài đặt mới | Người mới chạy `make demo` theo README trong dưới 15 phút |
| Training | Cùng dữ liệu và seed cho ra cùng chỉ số model |

## Kiến trúc

```
Postgres (core banking) ──Debezium──▶ Kafka ──┬──▶ Spark ──▶ Iceberg bronze ──dbt──▶ silver ──▶ gold features
                                               │                                                  │
                                               └──▶ Flink SQL velocity ──▶ Feast push ──▶ Redis   │ Feast offline
                                                                                   │              ▼
                                       client ──▶ Scoring API (FastAPI + ONNX) ◀───┘     Training (LightGBM)
                                                       │        ▲                                 │
                                                       │        └──── MLflow registry ◀───────────┘
                                                       ▼
                                          txn.scored ──▶ Iceberg ──▶ Evidently drift, skew check, Grafana
```

Các quyết định chính và lý do nằm trong [`docs/decisions/`](decisions/README.md).

## Ngoài phạm vi

- Triển khai nhiều node hoặc high availability cho Kafka, Flink, Trino hay Airflow.
- Apache Ranger và HashiCorp Vault (ADR-007 giải thích các phương án thay thế nhẹ hơn).
- Giao diện quản lý case cho analyst; kết quả review được mô phỏng từ nhãn của dataset.
- Graph feature và graph neural network (ghi nhận là hướng phát triển sau).
- Bất kỳ dữ liệu khách hàng thật nào.
