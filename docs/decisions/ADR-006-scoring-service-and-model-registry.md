# ADR-006: Scoring service FastAPI + ONNX với champion/challenger trên MLflow

## Trạng thái
Đã chấp nhận

## Ngày
2026-10-11

## Bối cảnh
Luồng cấp phép thanh toán phải chờ quyết định gian lận, nên việc chấm điểm phải đồng bộ và nhanh (p99 < 50 ms trên máy local). Service cũng phải:

- đổi phiên bản model mà không cần deploy lại, và rollback nhanh như vậy;
- chạy model mới ở chế độ shadow bên cạnh model hiện tại trước khi nó được ra quyết định thật;
- tiếp tục trả lời khi một thành phần phụ thuộc bị lỗi;
- ghi lại chính xác model nào và giá trị feature nào đã tạo ra mỗi quyết định.

## Quyết định
**Serving:** một service **FastAPI** riêng, cung cấp `POST /v1/score`, chạy model bằng **ONNX Runtime** và đọc feature từ Feast online (Redis). Kết quả trả về gồm `score`, `decision`, `reason_codes`, `model_version` và `fallback`. Hợp đồng API được quản lý version trong `serving/openapi.yaml`.

**Registry:** **MLflow** theo dõi mọi lần training và lưu model trong registry. Service nạp phiên bản gắn alias `champion`, và có thể chấm điểm thêm bằng `challenger` ở chế độ shadow (chỉ log, không dùng để ra quyết định). Promote nghĩa là chuyển alias, và chỉ diễn ra sau khi các validation gate trong CI (Task 4.4) đều đạt.

**Chính sách khi lỗi:** fail-open kèm rules. Nếu lấy feature hoặc suy luận model vượt timeout, service trả về quyết định theo rules với `fallback: true`, thay vì báo lỗi hay chặn mọi giao dịch.

**Audit:** mọi request được publish lên `txn.scored` kèm snapshot feature, điểm số, quyết định và phiên bản model.

## Các phương án đã cân nhắc

### Chạy model bên trong job Flink
- Ưu điểm: không thêm chặng mạng; điểm số được tạo ra dưới dạng stream.
- Nhược điểm: luồng cấp phép cần câu trả lời đồng bộ; việc rollout model bị gắn vào vòng đời của job streaming; shadow và rollback khó hơn.
- Loại vì: request/response mới là dạng mà luồng thanh toán cần.

### KServe hoặc Seldon làm tầng serving
- Ưu điểm: chuẩn serving model trên Kubernetes, hỗ trợ canary.
- Nhược điểm: cài đặt nặng trên laptop; che mất logic serving (lấy feature, rules, fallback) mà dự án muốn thể hiện.
- Chưa chọn lúc này. Service được triển khai lên Kubernetes bằng Helm và ArgoCD ở Task 4.5, thể hiện cùng các vấn đề triển khai với chi phí thấp hơn.

### Pickle model LightGBM và nạp bằng thư viện training
- Ưu điểm: không cần bước export.
- Nhược điểm: serving bị phụ thuộc phiên bản thư viện của môi trường training; suy luận chậm hơn; nạp pickle từ nguồn không tin cậy là không an toàn.
- Loại vì: ONNX cho artifact khả chuyển hơn, nhanh hơn và an toàn hơn.

## Hệ quả
- Đổi model là chuyển alias trên MLflow (và là một commit Git khi triển khai qua ArgoCD), nên rollback nhanh và có dấu vết audit.
- Chấm điểm shadow cho phép challenger chứng minh mình trên lưu lượng thật trước khi được promote.
- Fail-open giúp khách hàng thật không bị ảnh hưởng khi có sự cố, đổi lại có thể lọt một số gian lận trong lúc sự cố. Rules bao phủ các trường hợp rõ ràng nhất. Đánh đổi này được ghi rõ và có thể đảo ngược theo từng rule.
- Chi phí: service phải theo dõi hoặc được thông báo khi alias thay đổi, và nạp lại model an toàn mà không làm rớt request.
