# 日志数据分析与处理服务

基于 Python + MySQL + 多线程的访问日志清洗与分析服务，同时提供完整的 Web 分析仪表盘。

## 项目背景

业务系统每天产生海量访问日志，原始日志存在格式不统一、无效数据多、查询分析慢等问题。本项目实现一条可复用的日志处理流水线，将原始日志清洗后写入 MySQL，并输出多维度统计报表。

## 技术栈

- Python 3.10+
- ThreadPoolExecutor（线程池并行处理）
- PyMySQL（MySQL 驱动）
- DBUtils（数据库连接池）
- pytest（单元测试）

## 核心设计

### 1. 处理流水线

```
原始日志文件
    │
    ▼
逐行读取
    │
    ▼
cleaner.clean_line()  # 格式校验、字段标准化、无效数据过滤
    │
    ▼
批次聚合（每 1000 条）
    │
    ▼
ThreadPoolExecutor  # 4 个 worker 并行写库
    │
    ▼
analyzer.run_reports()  # SQL 多维度分析
```

### 2. 多线程优化

单线程逐条写入时，数据库往返延迟成为主要瓶颈。优化方案：

1. 使用 `ThreadPoolExecutor(max_workers=4)` 并行处理批次
2. 每个批次使用 `executemany` 批量插入，减少数据库往返
3. 使用 `PooledDB` 连接池复用连接，避免频繁建连/断连
4. 每个 worker 线程从池中获取独立连接，避免线程间共享连接导致的并发问题

处理 10 万条日志的总耗时从约 60 秒优化至约 15 秒。

### 3. 数据库设计

核心表 `access_logs`：

- `(log_date, status)` 联合索引：覆盖按日期+状态码的统计查询
- `(api_path)` 索引：覆盖热门接口 Top N 查询
- `(client_ip)` 索引：覆盖活跃 IP 分析

### 4. 分析报表

服务输出以下统计：

- 每日请求量、独立访客数、错误率趋势
- 热门 API Top 10
- 慢请求 Top 10
- 高频客户端 IP Top 10

## 快速启动

```bash
cd log-analysis-service
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 创建数据库和表
mysql -u root -p < schema.sql

# 配置环境变量
export DATABASE_URL="mysql+pymysql://root:password@localhost/log_analysis"

python main.py --file sample_data/access.log
```

## Web 仪表盘

项目内置了一个可直接运行的浏览器分析界面，无需先配置 MySQL：

```bash
cd log-analysis-service
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

python webapp.py
```

浏览器访问 `http://127.0.0.1:5001/`，包含以下功能：

- 概览页：总请求量、独立访客、错误率、平均响应等核心指标
- 4 类图表：请求趋势折线图、状态码环形图、热门接口条形图、响应时间分布图
- 每日趋势：按天统计请求量、访客、错误率、P95 响应时间
- 接口分析：Top API 调用量、性能与错误率排行
- 慢请求：响应时间最长的请求列表，定位性能瓶颈
- IP 分析：高频客户端 IP 流量与异常分析
- 日志浏览器：支持状态码、方法、IP、路径、响应时间多维筛选和分页
- 文件上传：拖拽或选择日志文件，自动清洗、并行写入并更新报表

首次启动时若没有历史数据，系统会自动生成 14 天演示日志，保证仪表盘开箱即可体验。上传真实日志后会追加到现有数据中。

### VS Code 调试

项目包含 `.vscode/launch.json`，使用 **Run Log Analysis Web** 配置按 `F5` 即可调试 Web 服务。

## 测试

```bash
pytest tests/
```

## API 概览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/stats` | 整体处理统计 |
| GET | `/api/reports/daily` | 每日汇总 |
| GET | `/api/reports/top-apis` | 热门接口排行 |
| GET | `/api/reports/slow-requests` | 慢请求列表 |
| GET | `/api/reports/top-ips` | 高频 IP 排行 |
| GET | `/api/reports/status-codes` | 状态码分布 |
| GET | `/api/logs` | 原始日志查询（分页+筛选） |
| POST | `/api/upload` | 上传并处理日志文件 |
| GET | `/api/health` | 健康检查 |
