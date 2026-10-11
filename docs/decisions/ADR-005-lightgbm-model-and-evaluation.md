# ADR-005: LightGBM kèm rules dự phòng, đánh giá bằng PR-AUC, recall tại FPR cố định và chi phí

## Trạng thái
Đã chấp nhận

## Ngày
2026-10-11

## Bối cảnh
Dữ liệu dạng bảng, mất cân bằng nặng (khoảng 0,5% gian lận) và có thứ tự thời gian. Model phải chấm điểm trong vài mili giây trên CPU, và mỗi quyết định cần kèm lời giải thích mà analyst đọc được.

Chọn chỉ số quan trọng ngang với chọn model. Accuracy vô nghĩa khi chỉ có 0,5% mẫu dương (đoán "không bao giờ gian lận" cũng được 99,5%), còn ROC-AUC trông đẹp quá mức trên dữ liệu mất cân bằng. Điều nghiệp vụ quan tâm là chặn được bao nhiêu gian lận với tỷ lệ chặn nhầm khách hàng thật chấp nhận được.

## Quyết định
**Model:** LightGBM, tuning bằng Optuna, xử lý mất cân bằng bằng class weight, export sang ONNX để serving.

**Đánh giá:**
- chỉ số chính: **PR-AUC**;
- chỉ số vận hành: **recall tại false positive rate 1%**;
- chỉ số kinh doanh: số tiền gian lận chặn được trừ chi phí review cố định cho mỗi false positive;
- luôn so sánh với model trước đó và với một rule ngưỡng số tiền đơn giản;
- chia dữ liệu nghiêm ngặt theo thời gian (xem SPEC).

**Giải thích:** trả về top 3 đóng góp SHAP làm reason codes cùng mỗi điểm số.

**Rules:** một bộ rule nhỏ, có version (`serving/config/rules.yaml`), xử lý các ràng buộc bắt buộc và làm phương án dự phòng khi model hoặc feature store không khả dụng.

Dataset: giao dịch thẻ mô phỏng Sparkov (xem SPEC).

## Các phương án đã cân nhắc

### XGBoost hoặc CatBoost
- Ưu điểm: độ chính xác tương đương; CatBoost xử lý biến phân loại sẵn.
- Nhược điểm: không có lợi thế rõ rệt trên dữ liệu này; LightGBM train nhanh hơn, quan trọng khi tuning trên laptop.
- Không chọn làm mặc định; có thể thêm làm challenger sau mà không phải đổi nền tảng.

### Deep learning (MLP, mô hình chuỗi, GNN)
- Ưu điểm: mô hình hoá được chuỗi giao dịch và đường dây gian lận.
- Nhược điểm: cần nhiều dữ liệu và công tuning hơn, suy luận chậm hơn, khó giải thích hơn; gradient boosting thường thắng trên dữ liệu bảng cỡ này.
- Chưa chọn lúc này; mô hình graph và chuỗi được ghi là hướng phát triển sau.

### Dataset PaySim hoặc IEEE-CIS
- Ưu điểm: PaySim mô phỏng chuyển tiền di động; IEEE-CIS lớn và sát thực tế.
- Nhược điểm: PaySim không có địa lý merchant; feature của IEEE-CIS bị ẩn danh nên không thể giải thích feature khi phỏng vấn.
- Loại vì: Sparkov có timestamp thật, mã thẻ và merchant, và toạ độ, đúng những gì velocity feature và feature khoảng cách cần.

## Hệ quả
- Suy luận nằm thoải mái trong ngân sách độ trễ trên CPU nhờ ONNX Runtime.
- Mọi phiên bản model được báo cáo với cùng bộ chỉ số và cùng baseline, nên các cải tiến so sánh được với nhau.
- Reason codes giúp mỗi quyết định giải thích được và hỗ trợ audit trail (ADR-007).
- Chi phí: tính SHAP lúc request làm tăng độ trễ; TreeSHAP trên LightGBM đủ nhanh, nhưng sẽ được đo trong load test và có thể chuyển sang bất đồng bộ nếu cần.
