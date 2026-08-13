# 日志数据分析与处理服务

基于 Python + MySQL + 多线程的访问日志清洗与分析服务。

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

## 测试

```bash
pytest tests/
```

