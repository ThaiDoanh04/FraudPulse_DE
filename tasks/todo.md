# Task List: Real-time Fraud Detection Platform (portfolio)

Kế hoạch tổng thể: `tasks/plan.md`. Definition of Done cho mọi task: test xanh trong CI, README của thư mục được cập nhật, không commit secret hay dữ liệu thô.

Cấu trúc repo:

```
infra/          docker-compose.yml (profiles), helm/, argocd/, kind/
source/         postgres schema, replay script
ingestion/      debezium connector, avro schemas
lakehouse/      spark jobs, dbt project, expectations
features/       feast repo
streaming/      flink sql jobs
training/       pipeline, evaluate, register, gates
serving/        fastapi app, loadtest
monitoring/     grafana dashboards, prometheus rules, drift job
orchestration/  airflow dags
docs/           SPEC.md, decisions/, results.md
```

---

## Phase 0: Nền móng (tuần 1)

### Task 0.1: SPEC ngắn + 7 ADR

**Description:** Viết SPEC 1–2 trang: bài toán, dataset, chỉ số mục tiêu. Viết 7 ADR liệt kê trong `plan.md`.

**Acceptance criteria:**
- [x] SPEC có chỉ số mục tiêu: PR-AUC, recall tại FPR 1%, p99 latency `/score` < 50ms trên máy local, throughput ≥ 500 req/s
- [x] 7 ADR theo cùng mẫu (Context, Decision, Alternatives, Consequences)

**Verification:**
- [x] Tests pass: `python3 -m pytest tests/test_docs.py`
- [ ] Manual check (người làm dự án): đọc lại mỗi ADR và trả lời được "tại sao không chọn phương án kia" trong 1 phút

**Dependencies:** None
**Files likely touched:** `docs/SPEC.md`, `docs/decisions/ADR-00{1..7}-*.md`
**Estimated scope:** S

### Task 0.2: Repo + docker-compose profiles + CI

**Description:** Khởi tạo repo, `docker-compose.yml` với profiles `core`, `streaming`, `ml`, `obs`, `gov`; Makefile; GitHub Actions chạy lint + test.

**Acceptance criteria:**
- [ ] `make up-core` dựng Postgres, Kafka, Schema Registry, MinIO, Iceberg REST catalog, Trino
- [ ] Mỗi service có giới hạn memory; `make down` dọn sạch volume
- [ ] CI chạy ruff + mypy + pytest; pre-commit có gitleaks

**Verification:**
- [ ] Build succeeds: `make up-core && make smoke`
- [ ] Tests pass: GitHub Actions xanh ở commit đầu

**Dependencies:** None
**Files likely touched:** `infra/docker-compose.yml`, `Makefile`, `.github/workflows/ci.yml`, `.pre-commit-config.yaml`, `pyproject.toml`
**Estimated scope:** M

### Task 0.3: Dataset + chia tập theo thời gian

**Description:** Script tải dataset, nạp vào bảng `transactions_history` trong Postgres. Chốt mốc thời gian: dữ liệu trước mốc dùng để train, sau mốc dùng để replay như giao dịch "đang diễn ra".

**Acceptance criteria:**
- [ ] Script tải và nạp idempotent (chạy lại không nhân đôi dữ liệu)
- [ ] Mốc thời gian ghi trong SPEC; tỷ lệ gian lận mỗi phần được báo cáo

**Verification:**
- [ ] Tests pass: `pytest source/tests`
- [ ] Manual check: `select count(*), avg(is_fraud)` khớp số liệu dataset gốc

**Dependencies:** 0.2
**Files likely touched:** `source/load_dataset.py`, `source/schema.sql`, `source/tests/`
**Estimated scope:** S

## Checkpoint 0
- [ ] `make up-core` chạy, CI xanh, dữ liệu nằm trong Postgres
- [ ] Tự review: còn muốn đổi gì ở ADR không?

---

## Phase 1: Walking skeleton (tuần 2–3)

### Task 1.1: Replay → Postgres → Debezium → Kafka

**Description:** Script replay chèn giao dịch vào bảng `transactions` theo đúng khoảng cách thời gian gốc (có hệ số tăng tốc). Debezium bắt thay đổi, ghi ra topic `txn.raw` dạng Avro. Số thẻ được hash (SHA-256 + salt) bằng SMT hoặc bước chuyển đổi trước khi ghi Kafka.

**Acceptance criteria:**
- [ ] Hệ số tăng tốc cấu hình được (ví dụ 60× = 1 giờ dữ liệu trong 1 phút)
- [ ] Topic `txn.raw` có schema đăng ký trong Schema Registry
- [ ] Không có số thẻ gốc trong Kafka

**Verification:**
- [ ] Tests pass: `pytest source/tests/test_replay.py ingestion/tests`
- [ ] Manual check: số message trong `txn.raw` bằng số dòng đã chèn

**Dependencies:** Checkpoint 0
**Files likely touched:** `source/replay.py`, `ingestion/connectors/postgres-txn.json`, `ingestion/schemas/transaction_v1.avsc`
**Estimated scope:** M

### Task 1.2: Kafka → Iceberg bronze + dbt silver

**Description:** Spark Structured Streaming đọc `txn.raw`, ghi bảng Iceberg `bronze.transactions`. dbt-trino tạo `silver.transactions` (chuẩn hoá kiểu, loại trùng).

**Acceptance criteria:**
- [ ] Đếm bronze = đếm Kafka sau khi flush
- [ ] Silver không trùng `trans_num`; kiểu dữ liệu đúng

**Verification:**
- [ ] Tests pass: `dbt test --select silver`
- [ ] Manual check: truy vấn qua Trino CLI

**Dependencies:** 1.1
**Files likely touched:** `lakehouse/spark/kafka_to_bronze.py`, `lakehouse/dbt/models/silver/*.sql`, `lakehouse/dbt/models/silver/schema.yml`
**Estimated scope:** M

### Task 1.3: Một feature → model baseline → MLflow

**Description:** Định nghĩa 1 feature view trong Feast (ví dụ số tiền trung bình 30 ngày của thẻ), materialize lên Redis. Train LightGBM baseline trên dữ liệu lịch sử, log MLflow, export ONNX, gán alias `champion`.

**Acceptance criteria:**
- [ ] Test point-in-time: feature tại thời điểm T không dùng dữ liệu sau T
- [ ] Model ONNX trong MLflow registry, có danh sách feature và alias `champion`

**Verification:**
- [ ] Tests pass: `pytest features/tests training/tests`
- [ ] Manual check: MLflow UI hiển thị run và model version

**Dependencies:** 1.2
**Files likely touched:** `features/feature_repo/*.py`, `features/feature_store.yaml`, `training/train.py`, `training/register.py`
**Estimated scope:** M

### Task 1.4: Scoring service `/score` tối thiểu

**Description:** FastAPI nhận giao dịch, lấy feature từ Feast online, chạy model `champion` bằng ONNX Runtime, trả score. Chốt OpenAPI v1.

**Acceptance criteria:**
- [ ] `POST /v1/score` trả `score`, `model_version`, `decision`
- [ ] Container khởi động tự load model từ MLflow

**Verification:**
- [ ] Tests pass: `pytest serving/tests`
- [ ] Manual check: `curl` với 1 giao dịch trả kết quả

**Dependencies:** 1.3
**Files likely touched:** `serving/app/main.py`, `serving/app/model.py`, `serving/app/features.py`, `serving/Dockerfile`, `serving/tests/`
**Estimated scope:** M

## Checkpoint 1
- [ ] Một giao dịch từ Postgres đi hết vòng tới score
- [ ] Quay GIF demo đầu tiên; ghi lại lỗi tích hợp đã gặp vào `docs/lessons.md` (chất liệu tốt cho phỏng vấn)

---

## Phase 2: Batch ML đúng chuẩn (tuần 4–5)

### Task 2.1: Data quality + Airflow DAG

**Description:** Great Expectations kiểm tra silver/gold (null, phạm vi `amt`, toạ độ hợp lệ, độ tươi dữ liệu). Airflow DAG: dbt run → kiểm tra DQ → Feast materialize. DQ fail thì dừng.

**Acceptance criteria:**
- [ ] Expectation suite cho mỗi bảng silver/gold
- [ ] DQ fail làm DAG dừng trước bước materialize

**Verification:**
- [ ] Tests pass: `pytest orchestration/tests` (DAG import)
- [ ] Manual check: chèn dữ liệu lỗi có chủ đích, DAG dừng và báo lỗi

**Dependencies:** Checkpoint 1
**Files likely touched:** `lakehouse/expectations/`, `orchestration/dags/batch_features.py`
**Estimated scope:** M

### Task 2.2: Gold features + Feast

**Description:** dbt tạo bảng feature gold: theo thẻ (số tiền trung bình/độ lệch 7–30 ngày, số giao dịch, tuổi khách), theo merchant (tỷ lệ gian lận lịch sử có độ trễ, category), địa lý (khoảng cách khách–merchant), thời gian (giờ trong ngày, cuối tuần). Đăng ký vào Feast.

**Acceptance criteria:**
- [ ] 15–25 feature, mỗi feature có mô tả trong `schema.yml`
- [ ] Feature dựa trên nhãn (tỷ lệ gian lận merchant) chỉ dùng nhãn đã có trước thời điểm giao dịch
- [ ] Test point-in-time cho mọi feature view

**Verification:**
- [ ] Tests pass: `dbt test --select gold` và `pytest features/tests`

**Dependencies:** 2.1
**Files likely touched:** `lakehouse/dbt/models/gold/feat_*.sql`, `features/feature_repo/*.py`, `features/tests/`
**Estimated scope:** M

### Task 2.3: Training pipeline + báo cáo đánh giá + model card

**Description:** Pipeline tái lập được: lấy training set qua Feast, split theo thời gian, class weight, Optuna tuning, đánh giá, sinh báo cáo HTML và model card, đăng ký MLflow.

**Acceptance criteria:**
- [ ] Báo cáo có: PR-AUC, recall@FPR 1%, đường cong PR, confusion matrix theo ngưỡng, cost theo số tiền, top SHAP features
- [ ] So sánh với baseline (Task 1.3) và một rule đơn giản (ví dụ `amt` > ngưỡng)
- [ ] Chạy lại cùng seed cho cùng kết quả

**Verification:**
- [ ] Tests pass: `pytest training/tests`
- [ ] Manual check: kết quả được chép vào `docs/results.md`

**Dependencies:** 2.2
**Files likely touched:** `training/pipeline.py`, `training/evaluate.py`, `training/report.py`, `training/model_card.py`
**Estimated scope:** M

## Checkpoint 2
- [ ] Model v1 vượt baseline và rule; có bảng số liệu
- [ ] Tự kiểm tra rò rỉ: nếu PR-AUC cao bất thường (> 0,95) thì truy lại feature trước khi đi tiếp

---

## Phase 3: Real-time (tuần 6–7)

### Task 3.1: Flink SQL velocity features → Redis

**Description:** Flink SQL đọc `txn.raw`, tính theo thẻ: số giao dịch và tổng tiền trong 10 phút / 1 giờ / 24 giờ, số merchant khác nhau trong 1 giờ, khoảng cách và thời gian từ giao dịch trước. Kết quả ghi topic `feat.velocity`; một consumer nhỏ đẩy vào Feast online qua push API. Ghi song song vào Iceberg để training dùng chung định nghĩa.

**Acceptance criteria:**
- [ ] Dùng event-time + watermark; giao dịch đến muộn được xử lý đúng
- [ ] Độ trễ từ event tới Redis p95 < 1 giây (đo bằng timestamp)
- [ ] Restart job từ checkpoint không đếm trùng

**Verification:**
- [ ] Tests pass: test SQL trên tập nhỏ với kết quả kỳ vọng tính tay
- [ ] Manual check: dừng/khởi động lại job, so số liệu

**Dependencies:** Checkpoint 2
**Files likely touched:** `streaming/velocity.sql`, `streaming/push_to_feast.py`, `features/feature_repo/velocity.py`
**Estimated scope:** M

### Task 3.2: `/score` dùng feature real-time + rules fallback

**Description:** Retrain model v2 có velocity features (bản offline tính cùng logic). Service đọc cả batch và velocity features; timeout feature store hoặc model lỗi thì trả quyết định từ rules.

**Acceptance criteria:**
- [ ] v2 vượt v1 trên cùng tập test; cập nhật `docs/results.md`
- [ ] Response có trường `fallback: true/false` và `reason_codes` (top 3 SHAP)

**Verification:**
- [ ] Tests pass: `pytest serving/tests` gồm test fallback
- [ ] Manual check: tắt Redis, `/score` vẫn trả trong < 50ms với `fallback: true`

**Dependencies:** 3.1
**Files likely touched:** `serving/app/*.py`, `training/pipeline.py`, `serving/config/rules.yaml`
**Estimated scope:** M

### Task 3.3: Kiểm tra train/serve skew

**Description:** Job so sánh feature online đã log lúc chấm điểm với feature tính lại offline cho cùng giao dịch.

**Acceptance criteria:**
- [ ] Báo cáo % mẫu lệch theo từng feature; ≥ 99% khớp trong dung sai

**Verification:**
- [ ] Tests pass: `pytest monitoring/tests/test_skew.py`

**Dependencies:** 3.2
**Files likely touched:** `monitoring/skew_check.py`
**Estimated scope:** S

### Task 3.4: Load test + chaos test

**Description:** Locust bắn `/score` ở nhiều mức tải; kịch bản lỗi: tắt Redis, tắt Flink, model không load được.

**Acceptance criteria:**
- [ ] Biểu đồ latency p50/p95/p99 theo throughput trong `docs/results.md`
- [ ] Mỗi kịch bản lỗi có kết quả ghi lại

**Verification:**
- [ ] Manual check: số liệu đạt mục tiêu SPEC hoặc ghi rõ lý do và hướng tối ưu

**Dependencies:** 3.2
**Files likely touched:** `serving/loadtest/locustfile.py`, `docs/results.md`
**Estimated scope:** S

## Checkpoint 3
- [ ] Có số liệu p99 latency, throughput, PR-AUC v1/v2 để ghi CV
- [ ] GIF demo thứ hai: giao dịch dồn dập bị chặn nhờ velocity features

---

## Phase 4: MLOps (tuần 8–10)

### Task 4.1: Metrics + log dự đoán

**Description:** Service expose metric Prometheus; Grafana dashboard. Mỗi lần chấm điểm ghi `txn.scored` (txn, score, model_version, feature snapshot, latency) → Iceberg.

**Acceptance criteria:**
- [ ] Dashboard: QPS, latency percentiles, tỷ lệ fallback, phân phối score
- [ ] 100% request có bản ghi trong `txn.scored`

**Verification:**
- [ ] Manual check: chạy replay 10 phút, dashboard và bảng Iceberg khớp số lượng

**Dependencies:** Checkpoint 3
**Files likely touched:** `serving/app/metrics.py`, `serving/app/audit.py`, `monitoring/grafana/*.json`, `monitoring/prometheus.yml`
**Estimated scope:** M

### Task 4.2: Drift monitoring

**Description:** Job Evidently (chạy qua Airflow) so phân phối feature và score của ngày gần nhất với tập tham chiếu. Kèm kịch bản drift giả lập (ví dụ tăng số tiền giao dịch hoặc đổi tỷ lệ category) để demo alert.

**Acceptance criteria:**
- [ ] Báo cáo drift HTML hằng ngày; metric drift đẩy sang Prometheus
- [ ] Bật kịch bản drift giả lập thì alert Grafana bắn

**Verification:**
- [ ] Manual check: chụp màn hình alert cho README

**Dependencies:** 4.1
**Files likely touched:** `monitoring/drift_job.py`, `orchestration/dags/drift.py`, `monitoring/alerts.yml`, `source/drift_scenario.py`
**Estimated scope:** M

### Task 4.3: CI: test + build + push image

**Description:** GitHub Actions: lint, unit test, dbt test trên dữ liệu mẫu nhỏ, build image `serving` và `streaming`, push GHCR khi merge vào `main`.

**Acceptance criteria:**
- [ ] PR không xanh thì không merge được (branch protection)
- [ ] Image gắn tag theo commit SHA

**Verification:**
- [ ] Manual check: mở PR cố tình làm hỏng test → CI đỏ

**Dependencies:** Checkpoint 3 (song song 4.1)
**Files likely touched:** `.github/workflows/ci.yml`, `.github/workflows/build.yml`
**Estimated scope:** S

### Task 4.4: CT: retrain → gates → promote

**Description:** Workflow retrain (chạy tay hoặc khi drift alert): train → validation gates (PR-AUC không thấp hơn champion quá ngưỡng, latency suy luận, không có feature mới chưa đăng ký) → đăng ký `challenger` → promote bằng cách đổi alias sau khi duyệt.

**Acceptance criteria:**
- [ ] Model không qua gate không thể thành `champion`
- [ ] Service tự reload model khi alias đổi, không restart

**Verification:**
- [ ] Tests pass: `pytest training/tests/test_gates.py`
- [ ] Manual check: thử promote một model cố tình yếu → bị chặn

**Dependencies:** 4.2, 4.3
**Files likely touched:** `training/gates.py`, `.github/workflows/retrain.yml`, `serving/app/model.py`
**Estimated scope:** M

### Task 4.5: Helm + kind + ArgoCD

**Description:** Helm chart cho scoring service (và Redis); cluster kind local; ArgoCD theo dõi thư mục `infra/helm` trong repo. Các service nặng (Kafka, Flink, lakehouse) vẫn ở docker-compose.

**Acceptance criteria:**
- [ ] Đổi image tag hoặc model alias bằng một commit → ArgoCD tự sync
- [ ] Rollback bằng revert commit

**Verification:**
- [ ] Manual check: quay GIF quá trình đổi version qua ArgoCD

**Dependencies:** 4.3
**Files likely touched:** `infra/helm/scoring/`, `infra/argocd/app.yaml`, `infra/kind/cluster.yaml`
**Estimated scope:** M
**Ghi chú:** Có thể lùi nếu trễ tiến độ, nhưng nên làm vì GitOps là điểm cộng lớn trên CV.

## Checkpoint 4
- [ ] Vòng đầy đủ: drift alert → retrain → gate → promote → deploy, chạy được
- [ ] Tự review: mỗi tầng trong sơ đồ kiến trúc đều có phần chạy thật

---

## Phase 5: Governance + showcase (tuần 11–12)

### Task 5.1: Lineage + phân quyền + audit trail

**Description:** OpenMetadata (profile `gov`) thu metadata và lineage từ dbt, Trino, Kafka. Trino file-based access control: vai trò `analyst` không đọc được bảng có trường nhạy cảm. Với một `txn_id`, truy vấn ra được model version, feature, score, quyết định.

**Acceptance criteria:**
- [ ] Lineage hiển thị từ bảng Postgres nguồn tới bảng feature gold
- [ ] User `analyst` bị từ chối khi truy vấn bảng bronze
- [ ] Truy vấn audit 1 giao dịch trả đủ thông tin

**Verification:**
- [ ] Manual check: chụp màn hình lineage và kết quả truy vấn audit cho README

**Dependencies:** Checkpoint 4
**Files likely touched:** `infra/openmetadata/`, `infra/trino/rules.json`, `docs/governance.md`, `lakehouse/dbt/models/audit/*.sql`
**Estimated scope:** M

### Task 5.2: README + demo + kết quả

**Description:** README tiếng Anh: sơ đồ kiến trúc, lý do chọn công nghệ (link ADR), cách chạy, bảng kết quả, ảnh/GIF demo, phần "Lessons learned". Lệnh `make demo` dựng hệ thống và chạy kịch bản trình diễn.

**Acceptance criteria:**
- [ ] `make demo` từ máy sạch chạy được theo README
- [ ] Bảng kết quả: PR-AUC v1/v2, recall@FPR 1%, p99 latency, throughput, độ trễ feature real-time
- [ ] Có 3–4 dòng mô tả dự án viết sẵn cho CV, mỗi dòng có số liệu

**Verification:**
- [ ] Manual check: nhờ một người khác clone và chạy theo README

**Dependencies:** 5.1
**Files likely touched:** `README.md`, `docs/architecture.png`, `docs/results.md`, `Makefile`
**Estimated scope:** S

## Checkpoint cuối
- [ ] Người lạ chạy được `make demo` trong < 15 phút
- [ ] Mọi tầng trong sơ đồ kiến trúc có bằng chứng (ảnh, số liệu, hoặc link code)
