# ADR-004: Flink SQL cho velocity feature streaming

## Trạng thái
Đã chấp nhận

## Ngày
2026-10-11

## Bối cảnh
Tín hiệu gian lận mạnh nhất là **velocity feature**: số giao dịch của một thẻ trong 10 phút qua, tổng số tiền trong 1 giờ qua, số merchant khác nhau trong 1 giờ qua, khoảng cách và thời gian kể từ giao dịch trước. Thẻ bị đánh cắp thường bị dùng dồn dập trong thời gian ngắn, và feature batch làm mới mỗi giờ không thể nhìn thấy điều đó.

Các feature này cần:

- ngữ nghĩa event-time (cửa sổ tính theo thời điểm giao dịch xảy ra, không phải lúc nó đến hệ thống);
- xử lý đúng sự kiện đến muộn bằng watermark;
- state theo từng thẻ, giữ được qua các lần khởi động lại mà không đếm trùng;
- độ tươi end-to-end dưới một giây.

## Quyết định
Dùng **Apache Flink** (một JobManager, một TaskManager) với job viết bằng **Flink SQL**. Job đọc `txn.raw`, tính các tổng hợp theo cửa sổ với key là thẻ, và ghi kết quả ra `feat.velocity`. Một consumer nhỏ đẩy kết quả vào Feast (online), và cùng kết quả đó được ghi vào Iceberg để training dùng đúng các giá trị giống hệt.

Bật checkpoint để job khởi động lại tiếp tục từ state nhất quán.

## Các phương án đã cân nhắc

### Spark Structured Streaming
- Ưu điểm: đã có trong stack để ghi bronze; chỉ cần học một engine.
- Nhược điểm: chạy theo micro-batch nên độ trễ cao hơn; logic có state theo từng key kém tự nhiên hơn Flink.
- Loại vì: độ tươi dưới một giây và state theo từng sự kiện là thế mạnh cốt lõi của Flink.

### Tính tổng hợp ngay lúc request trong scoring API
- Ưu điểm: không cần job streaming; luôn có dữ liệu mới nhất.
- Nhược điểm: mỗi lần chấm điểm phải quét lịch sử gần đây của thẻ trong database, vượt ngân sách độ trễ khi tải cao; logic bị lặp lại bên ngoài feature store.
- Loại vì: đẩy phần việc nặng vào đường xử lý nhạy cảm nhất về độ trễ.

### Kafka Streams
- Ưu điểm: là thư viện chứ không phải cluster; quản lý state theo key tốt.
- Nhược điểm: phải viết code ứng dụng JVM (Java/Kotlin) thay vì SQL; ít liên kết với các phần Python của dự án.
- Loại vì: Flink SQL giữ logic feature ở dạng khai báo, dễ đọc.

## Hệ quả
- Velocity feature được định nghĩa một lần bằng SQL, và cả giá trị online lẫn offline đều đến từ cùng một job.
- Độ tươi đo được trực tiếp (event time so với thời điểm ghi vào Redis).
- Chi phí: Flink là thành phần khó debug nhất. Giảm thiểu bằng cách bắt đầu với Flink SQL (không dùng DataStream API), test trên đầu vào nhỏ cố định với kết quả kỳ vọng tính tay, và để Flink sang Phase 3 sau khi luồng batch đã chạy.
- Backfill velocity feature lịch sử cho training được thực hiện bằng cách chạy cùng câu SQL ở chế độ batch trên bảng bronze.
