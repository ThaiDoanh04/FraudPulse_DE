# ADR-007: Governance ở quy mô portfolio

## Trạng thái
Đã chấp nhận

## Ngày
2026-10-11

## Bối cảnh
Một nền tảng chống gian lận thật xử lý dữ liệu cá nhân và đưa ra quyết định ảnh hưởng tới khách hàng, nên cần bảo vệ dữ liệu, phân quyền, lineage, kiểm soát chất lượng dữ liệu và audit trail. Bộ công cụ doanh nghiệp đầy đủ cho việc này (Apache Ranger, HashiCorp Vault, một nền tảng metadata đầy đủ) quá nặng để chạy cùng mọi thứ khác trên một laptop, và sẽ lấy mất thời gian của phần nền tảng cốt lõi.

Dataset là mô phỏng, nhưng chứa các trường có dạng PII thật (số thẻ, tên, địa chỉ, ngày sinh). Dự án xử lý chúng như dữ liệu thật, vì chính thói quen này là điều cần thể hiện.

## Quyết định
Giữ mọi khía cạnh governance, mỗi khía cạnh dùng công cụ nhẹ nhất vẫn thể hiện được nó:

| Khía cạnh | Cách thực hiện |
|---|---|
| Bảo vệ PII | Số thẻ được thay bằng token SHA-256 có salt trước khi dữ liệu vào Kafka; bỏ tên và địa chỉ; ngày sinh được quy đổi thành tuổi tại thời điểm giao dịch ở tầng silver. Salt lấy từ biến môi trường, không bao giờ nằm trong repo. |
| Chất lượng dữ liệu | Bộ kiểm tra Great Expectations cho silver và gold; một bộ kiểm tra fail sẽ dừng DAG Airflow trước khi feature được materialize. |
| Lineage và catalog | dbt docs cho lineage ở mức model; OpenMetadata (trong profile tuỳ chọn `gov`) cho lineage end-to-end qua Postgres, Kafka, Trino và dbt. |
| Phân quyền | File-based access control của Trino: vai trò `analyst` không đọc được bảng bronze và chi tiết audit. |
| Audit trail | Mọi lần chấm điểm được lưu kèm phiên bản model, snapshot feature, phiên bản rule và quyết định; một câu truy vấn tái tạo được bất kỳ quyết định nào từ `trans_num`. |
| Tài liệu model | Model card được sinh cùng mỗi phiên bản được đăng ký. |
| Secret | File `.env` bị loại khỏi Git, chỉ commit `.env.example`; gitleaks chạy trong pre-commit và CI. |

## Các phương án đã cân nhắc

### Bộ công cụ doanh nghiệp đầy đủ (Ranger, Vault, Atlas hoặc OpenMetadata luôn bật)
- Ưu điểm: gần nhất với cách ngân hàng thật triển khai.
- Nhược điểm: thêm nhiều service nặng tranh bộ nhớ với Kafka, Flink và Trino; mất hàng tuần cấu hình mà không cải thiện model hay pipeline.
- Loại vì: chi phí lớn hơn giá trị cho portfolio. Mỗi công cụ đều ứng với một phương án thay thế nhẹ hơn ở trên, và cách ánh xạ đó giải thích được khi phỏng vấn.

### Không có tầng governance
- Ưu điểm: làm nhanh nhất.
- Nhược điểm: bỏ sót một tầng mà dự án đã đặt mục tiêu bao phủ; số thẻ sẽ chạy dạng rõ qua mọi thành phần.
- Loại.

### Mã hoá PII thay vì hash
- Ưu điểm: người được phép có thể giải mã lại.
- Nhược điểm: cần quản lý khoá (chính là việc Vault làm); không feature nào cần số thẻ gốc.
- Loại vì: token tất định vẫn cho phép join và tổng hợp theo từng thẻ mà không bao giờ lưu giá trị gốc.

## Hệ quả
- Không thành phần nào sau tầng ingestion nhìn thấy số thẻ gốc, và điều này được kiểm tra bằng test (Task 1.1).
- Lineage, lỗi chất lượng dữ liệu, việc bị từ chối quyền truy cập và truy vấn audit đều có thể minh hoạ bằng ảnh chụp màn hình trong README.
- Hash với salt cố định là bút danh hoá (pseudonymisation), không phải ẩn danh hoá: ai có salt và một số thẻ nghi vấn thì xác nhận được trùng khớp. Chấp nhận được với dữ liệu mô phỏng; được ghi nhận là một giới hạn.
- Nếu sau này dự án chuyển thêm thành phần lên Kubernetes, Vault và một policy engine đầy đủ hơn có thể thay các phương án thay thế; khi đó một ADR mới sẽ thay thế ADR này.
