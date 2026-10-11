# ADR-002: Lakehouse Iceberg với Spark, dbt và Trino (mô hình medallion)

## Trạng thái
Đã chấp nhận

## Ngày
2026-10-11

## Bối cảnh
Nền tảng cần một nơi lưu trữ bền vững mọi giao dịch, nhãn và dự đoán để phục vụ training, đánh giá, phân tích drift và audit. Yêu cầu:

- truy cập bằng SQL cho biến đổi dữ liệu và phân tích ad-hoc;
- time travel, để tái tạo chính xác một tập training như tại thời điểm đã dùng;
- thay đổi schema mà không phải ghi lại dữ liệu;
- định dạng mở mà nhiều engine (Spark, Trino, Flink, Feast) đều đọc được;
- chạy được trên một máy với object storage.

## Quyết định
Lưu bảng dưới dạng **Apache Iceberg** trên **MinIO** (tương thích S3), dùng Iceberg REST catalog. Sử dụng:

- **Spark Structured Streaming** để ghi các topic Kafka vào bảng bronze;
- **dbt** (adapter dbt-trino) cho các biến đổi silver và gold, với test khai báo trong `schema.yml`;
- **Trino** làm SQL engine cho dbt, truy vấn ad-hoc và offline store của Feast.

Bảng được tổ chức theo mô hình medallion: `bronze` (dữ liệu thô, chỉ append, giữ nguyên như khi nhận), `silver` (đúng kiểu, đã loại trùng, an toàn về PII), `gold` (feature, nhãn, view phục vụ audit).

## Các phương án đã cân nhắc

### Dùng Postgres làm kho dữ liệu
- Ưu điểm: đã có sẵn trong stack; cách cài đặt đơn giản nhất.
- Nhược điểm: lẫn tải phân tích với vai trò "core banking"; không có time travel; không thể hiện được kỹ năng lakehouse.
- Loại vì: việc tách kho vận hành và kho phân tích là một phần dự án muốn thể hiện.

### Delta Lake
- Ưu điểm: trưởng thành, tích hợp Spark rất tốt.
- Nhược điểm: trải nghiệm tốt nhất gắn với Spark/Databricks; hỗ trợ Trino và Flink hẹp hơn Iceberg.
- Loại vì: Iceberg trung lập hơn giữa các engine, phù hợp với stack có cả Spark, Trino và Flink.

### DuckDB trên file Parquet
- Ưu điểm: cực nhẹ, nhanh cho phân tích một người dùng.
- Nhược điểm: không hỗ trợ nhiều writer đồng thời, không làm sink cho streaming, không có catalog dùng chung giữa các engine.
- Loại vì: không thể làm kho chung cho ingestion streaming và nhiều engine. Giữ lại như một lựa chọn cho notebook local.

## Hệ quả
- Tập training tái lập được bằng cách ghi snapshot id của Iceberg vào training run (log trong MLflow).
- dbt cho SQL có version, có test và tự sinh lineage, phần này được dùng lại cho governance ở ADR-007.
- Chi phí: MinIO, catalog, Spark và Trino khá nặng với laptop. Spark chỉ cần cho job ghi bronze; các biến đổi chạy trên Trino.
- Rủi ro: offline store Trino của Feast kém trưởng thành hơn file store. Nếu bị vướng, gold feature sẽ được export sang Parquet cho Feast, và ADR này được cập nhật.
