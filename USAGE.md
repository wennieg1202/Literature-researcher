# Literature Search Agent — 速查表

## 安装

```bash
git clone https://github.com/wennieg1202/Literature-researcher
cd Literature-researcher
git checkout claude/literature-search-agent-xbk2u
pip install -e .
```

配置 `.env`（本地文件，不上传 GitHub）：
```
ANTHROPIC_API_KEY=sk-ant-...
NOTION_API_KEY=your_key
NOTION_DATABASE_ID=your_db_id
```

---

## 使用

### 向导模式（推荐，全程方向键选择）

```bash
python -m lit_search --interactive
```

### 命令行直接调用

```bash
# 基础搜索
python -m lit_search "social capital"

# 指定模式 + 理论视角 + 保存到 Notion
python -m lit_search "professional jurisdiction" \
  --mode classic \
  --perspective profession \
  --save-notion

# 离线模式（无需学术 API，由 Claude 从训练知识生成文献）
python -m lit_search "institutional logics" --claude-only

# 查看所有理论视角
python -m lit_search --list-perspectives
```

---

## 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--mode` | `balanced` | `classic`（高被引）/ `frontier`（2020+）/ `balanced` |
| `--perspective` | 无 | `profession` / `organization` / `symbolic` / `stratification` / `network` / `culture` |
| `--max-papers N` | 150 | 最多输出 N 篇 |
| `--save-notion` | 关闭 | 推送到 Notion 数据库 |
| `--claude-only` | 关闭 | 跳过外部 API，由 Claude 直接生成文献（需核实 DOI）|
| `--include-abstract` | 关闭 | BibTeX 中包含摘要 |
| `--no-cache` | 关闭 | 强制重新抓取，不用缓存 |

---

## 输出

每次搜索生成一个 `.bib` 文件，可直接导入 Zotero / Mendeley。
启用 `--save-notion` 时同步写入 Notion 数据库。
