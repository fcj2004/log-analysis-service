"""Web dashboard for the log analysis service."""

import datetime
import io
import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import islice
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from analyzer.cleaner import clean_line
from config import Config

PROJECT_ROOT = Path(__file__).resolve().parent
UPLOAD_DIR = PROJECT_ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(
    __name__,
    static_folder=str(PROJECT_ROOT / "static"),
    static_url_path="/static",
)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB

# ---------------------------------------------------------------------------
# In-memory store. MySQL-backed mode can be added by replacing these
# functions with DatabasePool calls.
# ---------------------------------------------------------------------------
_store = {
    "logs": [],
    "stats": {
        "total_rows": 0,
        "invalid_rows": 0,
        "processing_time": 0,
        "last_file": None,
        "last_upload": None,
    },
    "lock": threading.Lock(),
}


def _row_to_dict(row):
    return {
        "log_time": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
        "client_ip": row[1],
        "request_method": row[2],
        "api_path": row[3],
        "status": row[4],
        "response_time_ms": row[5],
        "user_agent": row[6],
    }


def _dict_to_row(item):
    """Convert a JSON row back into the cleaner tuple shape."""
    log_time = datetime.datetime.fromisoformat(item["log_time"])
    return (
        log_time,
        item["client_ip"],
        item["request_method"],
        item["api_path"],
        int(item["status"]),
        int(item["response_time_ms"]),
        item["user_agent"],
    )


def _save_store():
    """Persist the in-memory store as JSON for demo continuity."""
    path = PROJECT_ROOT / "data_store.json"
    try:
        with _store["lock"]:
            payload = {
                "logs": [_row_to_dict(r) for r in _store["logs"][-5000:]],
                "stats": _store["stats"],
            }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except (OSError, TypeError, ValueError):
        pass


def _load_store():
    path = PROJECT_ROOT / "data_store.json"
    if not path.exists():
        _seed_demo_data()
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        with _store["lock"]:
            _store["logs"] = [_dict_to_row(i) for i in payload.get("logs", [])]
            _store["stats"].update(payload.get("stats", {}))
    except (OSError, ValueError, TypeError, KeyError):
        _seed_demo_data()


def _seed_demo_data():
    """Generate synthetic access log data so the dashboard is useful immediately."""
    ips = [
        "10.10.1.8", "10.10.2.11", "10.10.3.20", "10.10.4.3",
        "10.10.5.17", "10.10.6.29", "10.10.7.41",
    ]
    paths = [
        ("GET", "/api/products", 35, 200),
        ("GET", "/api/products?category=1", 28, 200),
        ("POST", "/api/orders", 180, 201),
        ("POST", "/api/auth/login", 95, 200),
        ("GET", "/api/messages", 45, 200),
        ("GET", "/api/orders?role=buyer", 52, 200),
        ("DELETE", "/api/messages/100", 20, 403),
        ("GET", "/api/products/9999", 12, 404),
        ("POST", "/api/upload", 220, 500),
        ("GET", "/api/reports/daily", 40, 200),
        ("PUT", "/api/profile", 70, 200),
        ("GET", "/api/health", 8, 200),
    ]
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)",
        "curl/8.0",
        "python-requests/2.31",
        "PostmanRuntime/7.36",
    ]
    now = datetime.datetime.now()
    rows = []
    for day_offset in range(14):
        day = now - datetime.timedelta(days=day_offset)
        for hour in range(0, 24, 2):
            for _ in range(random.randint(8, 25)):
                method, path, base_latency, base_status = random.choice(paths)
                # Some requests become slow or error.
                latency = base_latency * random.uniform(0.6, 3.5)
                status = base_status
                if random.random() < 0.04:
                    status = random.choice([500, 502, 503])
                if random.random() < 0.08:
                    latency *= 5
                log_time = day.replace(
                    hour=hour,
                    minute=random.randint(0, 59),
                    second=random.randint(0, 59),
                    microsecond=0,
                )
                rows.append((
                    log_time,
                    random.choice(ips),
                    method,
                    path,
                    status,
                    int(latency),
                    random.choice(agents),
                ))
    rows.sort(key=lambda r: r[0], reverse=True)
    with _store["lock"]:
        _store["logs"] = rows
        _store["stats"].update(
            total_rows=len(rows),
            invalid_rows=random.randint(20, 120),
            processing_time=round(random.uniform(10, 16), 2),
            last_file="sample_data/access.log",
            last_upload=datetime.datetime.now().isoformat(),
        )


def _process_rows(rows, stats):
    """Insert rows into the in-memory store using a small thread pool."""
    batch_size = Config.BATCH_SIZE

    def insert_batch(batch):
        with _store["lock"]:
            _store["logs"].extend(batch)
        return len(batch)

    started = time.perf_counter()
    total = 0
    with ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
        futures = []
        iterator = iter(rows)
        while True:
            batch = list(islice(iterator, batch_size))
            if not batch:
                break
            futures.append(executor.submit(insert_batch, batch))
        for future in as_completed(futures):
            total += future.result()
    stats["processing_time"] = round(time.perf_counter() - started, 2)
    stats["total_rows"] = total
    return total


def _parse_upload(content):
    """Parse uploaded log content and return cleaned rows plus invalid count."""
    valid = []
    invalid = 0
    text = content.decode("utf-8", errors="replace")
    for line in text.splitlines():
        if not line.strip():
            continue
        cleaned = clean_line(line)
        if cleaned is None:
            invalid += 1
        else:
            valid.append(cleaned)
    return valid, invalid


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/stats")
def get_stats():
    with _store["lock"]:
        logs = _store["logs"]
        stats = dict(_store["stats"])
    total = len(logs)
    errors = sum(1 for r in logs if r[4] >= 400)
    avg_latency = sum(r[5] for r in logs) / total if total else 0
    unique_ips = len({r[1] for r in logs})
    return jsonify({
        "code": 0,
        "data": {
            "total_requests": total,
            "unique_visitors": unique_ips,
            "error_count": errors,
            "error_rate": round(errors / total * 100, 2) if total else 0,
            "avg_response_ms": round(avg_latency, 1),
            "invalid_rows": stats.get("invalid_rows", 0),
            "processing_time": stats.get("processing_time", 0),
            "last_file": stats.get("last_file"),
            "last_upload": stats.get("last_upload"),
        },
    })


@app.get("/api/reports/daily")
def daily_summary():
    days = int(request.args.get("days", 14))
    with _store["lock"]:
        logs = list(_store["logs"])
    by_day = {}
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    for row in logs:
        if row[0] < cutoff:
            continue
        key = row[0].strftime("%Y-%m-%d")
        entry = by_day.setdefault(key, {
            "log_date": key,
            "requests": 0,
            "unique_visitors": set(),
            "error_count": 0,
            "response_times": [],
        })
        entry["requests"] += 1
        entry["unique_visitors"].add(row[1])
        if row[4] >= 400:
            entry["error_count"] += 1
        entry["response_times"].append(row[5])
    result = []
    for key in sorted(by_day, reverse=True):
        entry = by_day[key]
        result.append({
            "log_date": key,
            "requests": entry["requests"],
            "unique_visitors": len(entry["unique_visitors"]),
            "error_count": entry["error_count"],
            "error_rate": round(entry["error_count"] / entry["requests"] * 100, 2),
            "avg_response_ms": round(sum(entry["response_times"]) / len(entry["response_times"]), 1),
            "p95_response_ms": round(
                sorted(entry["response_times"])[int(len(entry["response_times"]) * 0.95)],
                1,
            ),
        })
    return jsonify({"code": 0, "data": result})


@app.get("/api/reports/top-apis")
def top_apis():
    limit = min(int(request.args.get("limit", 10)), 50)
    with _store["lock"]:
        logs = list(_store["logs"])
    by_path = {}
    for row in logs:
        key = row[3]
        entry = by_path.setdefault(key, {"hits": 0, "latencies": [], "errors": 0})
        entry["hits"] += 1
        entry["latencies"].append(row[5])
        if row[4] >= 400:
            entry["errors"] += 1
    result = sorted(by_path.items(), key=lambda kv: kv[1]["hits"], reverse=True)[:limit]
    return jsonify({
        "code": 0,
        "data": [{
            "api_path": path,
            "hits": entry["hits"],
            "avg_response_ms": round(sum(entry["latencies"]) / len(entry["latencies"]), 1),
            "error_rate": round(entry["errors"] / entry["hits"] * 100, 2),
        } for path, entry in result],
    })


@app.get("/api/reports/slow-requests")
def slow_requests():
    limit = min(int(request.args.get("limit", 20)), 100)
    with _store["lock"]:
        logs = list(_store["logs"])
    slow = sorted(logs, key=lambda r: r[5], reverse=True)[:limit]
    return jsonify({"code": 0, "data": [_row_to_dict(r) for r in slow]})


@app.get("/api/reports/top-ips")
def top_ips():
    limit = min(int(request.args.get("limit", 10)), 50)
    with _store["lock"]:
        logs = list(_store["logs"])
    by_ip = {}
    for row in logs:
        entry = by_ip.setdefault(row[1], {"requests": 0, "errors": 0, "latencies": []})
        entry["requests"] += 1
        if row[4] >= 400:
            entry["errors"] += 1
        entry["latencies"].append(row[5])
    result = sorted(by_ip.items(), key=lambda kv: kv[1]["requests"], reverse=True)[:limit]
    return jsonify({
        "code": 0,
        "data": [{
            "client_ip": ip,
            "requests": entry["requests"],
            "error_count": entry["errors"],
            "avg_response_ms": round(sum(entry["latencies"]) / len(entry["latencies"]), 1),
        } for ip, entry in result],
    })


@app.get("/api/reports/status-codes")
def status_codes():
    with _store["lock"]:
        logs = list(_store["logs"])
    counts = {}
    for row in logs:
        key = str(row[4])
        counts[key] = counts.get(key, 0) + 1
    return jsonify({
        "code": 0,
        "data": [{"status": int(k), "count": v} for k, v in sorted(counts.items())],
    })


@app.get("/api/logs")
def list_logs():
    page = max(int(request.args.get("page", 1)), 1)
    per_page = min(max(int(request.args.get("per_page", 50)), 1), 500)
    status_filter = request.args.get("status", type=int)
    method_filter = request.args.get("method")
    ip_filter = request.args.get("ip")
    path_filter = request.args.get("path", "").strip()
    min_latency = request.args.get("min_latency", type=int)

    with _store["lock"]:
        logs = list(_store["logs"])
    if status_filter:
        logs = [r for r in logs if r[4] == status_filter]
    if method_filter:
        logs = [r for r in logs if r[2].upper() == method_filter.upper()]
    if ip_filter:
        logs = [r for r in logs if ip_filter in r[1]]
    if path_filter:
        logs = [r for r in logs if path_filter in r[3]]
    if min_latency:
        logs = [r for r in logs if r[5] >= min_latency]

    total = len(logs)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = logs[start:end]
    return jsonify({
        "code": 0,
        "data": {
            "items": [_row_to_dict(r) for r in page_items],
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
        },
    })


@app.post("/api/upload")
def upload_log():
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"code": 400, "message": "no file uploaded"}), 400

    content = file.read()
    if not content:
        return jsonify({"code": 400, "message": "empty file"}), 400

    valid_rows, invalid_count = _parse_upload(content)
    if not valid_rows:
        return jsonify({
            "code": 400,
            "message": f"no valid log lines found (rejected {invalid_count} lines)",
        }), 400

    stats = {
        "invalid_rows": invalid_count,
        "last_file": file.filename,
        "last_upload": datetime.datetime.now().isoformat(),
    }
    inserted = _process_rows(valid_rows, stats)
    with _store["lock"]:
        _store["stats"].update(stats)
    _save_store()
    return jsonify({
        "code": 0,
        "data": {
            "inserted": inserted,
            "invalid": invalid_count,
            "processing_time": stats["processing_time"],
        },
    })


@app.get("/api/health")
def health():
    return jsonify({"code": 0, "status": "ok", "time": datetime.datetime.now().isoformat()})


_load_store()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)

