# Literature Search Agent — 使用速查表

## 安装

```bash
git clone https://github.com/wennieg1202/Literature-researcher
cd Literature-researcher
git checkout claude/literature-search-agent-xbk2u
pip install -e .
```

配置文件 `.env`（已在本地创建，不会上传 GitHub）：
```
NOTION_API_KEY=your_key
NOTION_DATABASE_ID=your_db_id
ANTHROPIC_API_KEY=sk-ant-...   # 可选，启用 Claude 查询扩展和摘要
```

---

## 最简单：交互向导（推荐）

```bash
python -m lit_search --interactive
```

全程用方向键选择，不需要记任何参数。

---

## 直接调用

### 基础搜索

```bash
# 关键词搜索
python -m lit_search "social capital"

# 研究问题搜索（效果更好）
python -m lit_search 'Why do elite networks reproduce inequality?'

# Boolean 查询
python -m lit_search '"institutional logics" AND (organizations OR fields)'
```

### 选择搜索目标

```bash
# 经典理论 — 高被引奠基文献
python -m lit_search "professional jurisdiction" --mode classic

# 前沿研究 — 2020年后发表
python -m lit_search "AI and organizations" --mode frontier

# 均衡（默认）
python -m lit_search "social capital" --mode balanced
```

### 选择社会学理论视角

```bash
# 职业社会学（Abbott, Freidson, Larson）
python -m lit_search "knowledge workers" --perspective profession

# 组织理论（DiMaggio, Powell, Meyer）
python -m lit_search "institutional change" --perspective organization

# 符号互动与文化社会学（Goffman, Bourdieu, Collins）
python -m lit_search "identity at work" --perspective symbolic

# 社会分层与不平等（Tilly, Lareau, Lamont）
python -m lit_search "educational inequality" --perspective stratification

# 社会网络分析（Granovetter, Burt, Lin）
python -m lit_search "network ties career mobility" --perspective network

# 知识社会学（Mannheim, Latour, Knorr Cetina）
python -m lit_search "science and technology studies" --perspective culture

# 查看所有视角
python -m lit_search --list-perspectives
```

### 保存到 Notion

```bash
# 搜索完后自动推送到 Notion 知识库
python -m lit_search "social capital" --save-notion

# 组合使用
python -m lit_search 'How does professional jurisdiction shape AI adoption?' \
  --mode frontier \
  --perspective profession \
  --save-notion \
  --max-papers 50
```

### 常用参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--max-papers N` | 150 | 输出最多 N 篇 |
| `--top-snowball N` | 20 | 从前 N 篇做引用追踪 |
| `--output FILE` | 自动生成 | 指定 .bib 文件路径 |
| `--include-abstract` | 关闭 | BibTeX 中包含摘要 |
| `--no-cache` | 关闭 | 不使用缓存，强制重新抓取 |

---

## 典型场景组合

```bash
# 1. 快速了解一个领域（15分钟）
python -m lit_search "your topic" --mode balanced --max-papers 30

# 2. 系统综述准备（深度）
python -m lit_search 'Your research question?' \
  --mode classic \
  --perspective organization \
  --max-papers 100 \
  --include-abstract \
  --save-notion

# 3. 追踪最新进展
python -m lit_search "your topic" \
  --mode frontier \
  --max-papers 50 \
  --save-notion

# 4. 写文献综述前的探索
python -m lit_search --interactive   # 一步步选，最后保存到 Notion
```

---

## 输出文件

每次搜索生成一个 `.bib` 文件，包含：
- 所有文献的 BibTeX 条目（可直接导入 Zotero / Mendeley）
- 底部附 Claude 生成的文献综述摘要（需要 `ANTHROPIC_API_KEY`）

如果启用了 `--save-notion`，同时在你的 Notion 数据库中创建对应条目，字段包括：
标题、作者、年份、DOI、期刊、摘要、引用数、搜索视角。
