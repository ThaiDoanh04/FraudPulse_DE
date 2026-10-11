# ADR-001: Kafka kết hợp Debezium CDC làm xương sống sự kiện

## Trạng thái
Đã chấp nhận

## Ngày
2026-10-11

## Bối cảnh
Giao dịch phát sinh trong một database vận hành (Postgres, đóng vai hệ thống core banking). Có hai bên tiêu thụ với yêu cầu rất khác nhau:

- luồng streaming, phải tính velocity feature trong vòng một giây sau khi giao dịch xảy ra;
- luồng batch, đưa mọi giao dịch vào lakehouse để training và audit.

Cả hai phải thấy cùng các sự kiện theo cùng thứ tự, và phải replay được lịch sử để tính lại feature sau khi sửa lỗi. Trong ngân hàng thật, ứng dụng nguồn thường không được phép sửa, nên sự kiện phải được bắt từ chính database.

## Quyết định
Dùng **Debezium** để bắt thay đổi ở mức dòng từ Postgres (logical replication) vào **Apache Kafka** (một broker, chế độ KRaft). Schema message dùng Avro, đăng ký trong **Schema Registry** với chế độ tương thích BACKWARD.

Topic chính là `txn.raw`. Các topic downstream đặt tên theo mẫu `<domain>.<stage>` (`feat.velocity`, `txn.scored`).

## Các phương án đã cân nhắc

### Ứng dụng ghi thẳng vào Kafka (dual write)
- Ưu điểm: không cần thành phần CDC; cấu trúc sự kiện đơn giản hơn.
- Nhược điểm: khi có lỗi, dữ liệu trong database và trong Kafka có thể lệch nhau; phải sửa ứng dụng nguồn, điều không thực tế với core banking.
- Loại vì: CDC đọc chính commit log của database nên nhất quán ngay từ thiết kế, và không cần sửa nguồn.

### Truy vấn database định kỳ (polling)
- Ưu điểm: dễ làm, chỉ cần một cột timestamp.
- Nhược điểm: độ trễ bằng chu kỳ polling; bỏ sót update và delete; tăng tải truy vấn lên nguồn.
- Loại vì: không đáp ứng được độ tươi feature dưới một giây.

### RabbitMQ hoặc một hàng đợi khác
- Ưu điểm: vận hành đơn giản hơn cho mô hình gửi nhận điểm-điểm.
- Nhược điểm: message bị xoá sau khi tiêu thụ nên không replay được; không có cơ chế giữ thứ tự theo key qua partition.
- Loại vì: replay và giữ thứ tự theo từng thẻ là yêu cầu cốt lõi.

## Hệ quả
- Một luồng sự kiện nuôi cả hai nhánh, nên dữ liệu training và dữ liệu serving xuất phát từ cùng các sự kiện.
- Có thể replay lịch sử từ Kafka (hoặc nạp lại từ Postgres) để backfill feature.
- Avro và Schema Registry làm cho thay đổi schema trở nên tường minh; thay đổi không tương thích bị chặn ngay lúc produce thay vì làm hỏng bảng downstream.
- Chi phí: Kafka, Schema Registry và Kafka Connect thêm ba container và tốn đáng kể bộ nhớ. Giảm thiểu bằng cách chỉ chạy chúng trong các Compose profile `core` và `streaming`.
- Debezium phát ra change envelope (`before`/`after`/`op`); cần một bước chuyển đổi để làm phẳng về schema `transaction_v1` (Task 1.1).
