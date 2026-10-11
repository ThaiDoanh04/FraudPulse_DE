# ADR-003: Feast làm feature store

## Trạng thái
Đã chấp nhận

## Ngày
2026-10-11

## Bối cảnh
Nguyên nhân phổ biến nhất khiến model gian lận hỏng trên production là **train/serve skew**: một feature được tính theo một cách trong notebook training và theo cách hơi khác trong code serving, nên model sau khi triển khai nhận đầu vào mà nó chưa từng được huấn luyện.

Một lỗi thứ hai, khó thấy hơn, là **rò rỉ dữ liệu (leakage)**: một dòng training được tạo từ thông tin chưa có tại thời điểm giao dịch xảy ra (ví dụ tỷ lệ gian lận của merchant tính trên toàn bộ dataset, kể cả nhãn tương lai). Chỉ số offline khi đó rất đẹp còn hiệu năng thật trên production thì sụp đổ.

Nền tảng cần mỗi feature chỉ có một định nghĩa, dùng cho cả training (dữ liệu lịch sử, đúng theo thời điểm) và serving (giá trị mới nhất, đọc trong vài mili giây).

## Quyết định
Dùng **Feast** với:

- **offline store**: Trino trên các bảng gold Iceberg (dự phòng: file Parquet, xem ADR-002);
- **online store**: Redis;
- **feature batch** được materialize từ bảng gold bằng Airflow;
- **feature streaming** được pipeline Flink ghi qua push API của Feast (ADR-004).

Tập training luôn được tạo bằng `get_historical_features` (point-in-time join theo event timestamp). Mỗi feature view có một test point-in-time, test này fail nếu giá trị tại thời điểm T phụ thuộc vào dữ liệu sau T.

## Các phương án đã cân nhắc

### Không dùng feature store (SQL cho training, tự viết lookup cho serving)
- Ưu điểm: ít thành phần nhất.
- Nhược điểm: mỗi feature có hai bản cài đặt; point-in-time join phải tự viết; skew dễ xảy ra và khó phát hiện.
- Loại vì: ngăn skew và rò rỉ chính là lý do tầng này tồn tại.

### Hopsworks
- Ưu điểm: nền tảng đầy đủ, có UI, online store và validation tích hợp.
- Nhược điểm: nặng khi tự host trên một máy; phần lớn giá trị trùng với các thành phần đã chọn.
- Loại vì: quá nặng so với quy mô dự án.

### Tecton hoặc feature store trên cloud
- Ưu điểm: dịch vụ được quản lý, hỗ trợ streaming tốt.
- Nhược điểm: thương mại hoặc chỉ chạy trên cloud; không chạy local được.
- Loại vì: dự án phải chạy hoàn toàn trên laptop.

## Hệ quả
- Định nghĩa feature nằm trong `features/feature_repo/` và được review như mọi đoạn code khác.
- Tính đúng point-in-time được đảm bảo bằng test, không dựa vào quy ước.
- Skew đo được: giá trị online được log lúc chấm điểm và so sánh với giá trị tính lại offline (Task 3.3).
- Chi phí: Feast thêm một registry và một bước materialize; dữ liệu Flink ghi vào online store phải đi qua thêm một chặng (push API) thay vì ghi thẳng vào Redis.
