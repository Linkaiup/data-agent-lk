# Data Agent Skill

面向 Codex 与 Claude Code 的可审计数据分析 Skill。它帮助智能体以自然语言处理本地表格文件和数据库：先理解数据，再执行受限的只读查询，最后保留 SQL、查询结果与报告作为证据。

## 功能

- 分析本地 CSV、JSON；Excel 与 Parquet 可通过可选读取器接入。
- 生成数据画像、Markdown 报告、查询结果 CSV 与 SVG 柱状图。
- 连接 PostgreSQL、MySQL、ClickHouse，读取 catalog 并执行单条只读 SQL。
- 使用 JSON 语义层固化表粒度、维度、指标和关联关系，并依据 catalog 校验。
- 默认限制数据库返回 1,000 行，拒绝写入、DDL、多语句 SQL。

## 安装

将 `data-agent` 目录复制到对应工具的用户级 Skills 目录：

```bash
# Codex
cp -R data-agent ~/.codex/skills/data-agent

# Claude Code
mkdir -p ~/.claude/skills
cp -R data-agent ~/.claude/skills/data-agent-skill
```

重启或开始一个新会话后，可以通过 `$data-agent` 调用该 Skill。在 Claude Code 中，如已有同名 Skill，则使用 `$data-agent-skill`。

## 快速开始

分析本地 CSV，并按地区汇总收入、生成柱状图：

```bash
python3 data-agent/scripts/analyze_data.py analyze path/to/sales.csv \
  --output-dir analysis/revenue-by-region \
  --chart bar --x region --y revenue
```

使用单条只读 SQL：

```bash
python3 data-agent/scripts/analyze_data.py analyze path/to/sales.csv \
  --output-dir analysis/top-customers \
  --sql 'SELECT customer, SUM(revenue) AS revenue FROM data GROUP BY customer ORDER BY revenue DESC'
```

每次运行都会输出：

- `profile.json`：数据行列、类型、缺失与去重概览。
- `analysis.sql`：实际执行的 SQL。
- `result.csv`：结论的数据依据。
- `report.md`：可分享的分析摘要。
- `chart.svg`：请求图表时生成。

## 数据库分析

数据库连接只通过环境变量提供，连接串、密码和令牌不会写入报告或日志。

```bash
export DATA_AGENT_POSTGRES_URL='postgresql://user:password@host:5432/database'
export DATA_AGENT_MYSQL_URL='mysql://user:password@host:3306/database'
export DATA_AGENT_CLICKHOUSE_URL='clickhouse://user:password@host:8123/database'
```

按需安装驱动：

```bash
pip install psycopg              # PostgreSQL
pip install pymysql              # MySQL
pip install clickhouse-connect   # ClickHouse
```

先导出数据目录，再查询：

```bash
python3 data-agent/scripts/analyze_data.py catalog \
  --source postgres --output-dir analysis/catalog

python3 data-agent/scripts/analyze_data.py query \
  --source postgres --output-dir analysis/revenue \
  --sql 'SELECT country, SUM(amount) AS revenue FROM orders GROUP BY country'
```

支持的 `--source`：`postgres`、`mysql`、`clickhouse`。

## 语义层

语义层是可提交到 Git 的 JSON 文件，用于保存业务定义，避免智能体只凭字段名猜测指标口径。可从 [示例文件](data-agent/assets/semantic-example.json) 开始：

```json
{
  "source": "postgres",
  "tables": {
    "orders": {
      "grain": "one row per order",
      "dimensions": { "country": "shipping_country" },
      "metrics": { "gross_revenue": "SUM(amount)" },
      "joins": []
    }
  }
}
```

在实际查询前校验表和维度字段：

```bash
python3 data-agent/scripts/analyze_data.py semantic-check semantic/orders.json \
  --catalog analysis/catalog/catalog.json
```

## 安全边界

- 仅允许单条 `SELECT` 或 `WITH` 查询；拒绝写入、DDL 与多语句。
- 数据库查询默认最多返回 1,000 行；可通过 `--max-rows` 调整。
- 优先以 catalog 与语义层作为业务上下文；结论应引用生成的 `result.csv` 与 `analysis.sql`。
- 不要把数据库连接串、密码、访问令牌写进仓库、Prompt、报告或语义层。

## 开发与测试

```bash
python3 -B -m unittest discover -s tests -v
```

项目结构：

```text
data-agent/
  SKILL.md                 # Agent 工作流与使用规范
  scripts/                 # 本地分析、SQL 安全、数据库与语义层模块
  assets/                  # 示例数据与语义层模板
tests/                     # 单元与集成测试
```

## License

本项目尚未声明许可证；在发布或接受外部贡献前，请补充 `LICENSE` 文件。
