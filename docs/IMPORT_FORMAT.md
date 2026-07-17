# EchoMind 导入格式规范

## 1. 阶段 3 边界

阶段 3 只实现本地文件路径到 Canonical Chat Schema 的确定性解析：识别格式、读取原始字节、计算 SHA-256、解析、统一验证并返回安全错误和统计。Parser 不修改源文件、不访问网络、不写数据库、不上传文件、不清洗正文，也不自动识别微信、QQ、WeFlow 或其他任意聊天导出。

三个已支持的通用格式是：

- `generic-json` 1.0：`.json`
- `generic-csv` 1.0：`.csv`
- `generic-text` 1.0：`.txt`

`weflow` 0.0 仅为不可用的接口边界，不属于支持格式。

## 2. Parser 契约与 Registry

```python
class ChatParser(Protocol):
    parser_name: str
    parser_version: str
    supported_extensions: frozenset[str]
    available: bool

    def can_parse(self, path: Path) -> bool: ...
    def parse(
        self, path: Path, options: ParserOptions | None = None
    ) -> ParsedChatFile: ...
    def validate(self, result: ParsedChatFile) -> ParsedChatFile: ...
```

Registry 先按小写扩展名筛选，再读取最多 8192 个原始字节做轻量签名识别，不完整解析文件。无候选返回 `unsupported_extension`，无签名匹配返回 `unsupported_format`，多个匹配返回 `ambiguous_format`；绝不按注册顺序静默选择。调用方可显式指定 `parser_name`，不存在的名称返回 `unknown_parser`。

## 3. Canonical Chat Schema

Canonical Schema 位于 `backend/src/echomind/parsers/schemas.py`，是独立 Pydantic 传输与验证结构，不是 ORM Model，也不导入数据库模块。

### CanonicalParticipant

| 字段 | 类型 | 规则 |
|---|---|---|
| `source_participant_id` | `string \| null` | 非空白；格式可用时必须提供 |
| `display_name` | `string` | 必填且不能只含空白 |
| `aliases` | `string[]` | 默认空数组；值非空白且不能重复 |
| `is_profile_owner` | `boolean \| null` | 仅使用源数据的明确声明；不按名称猜测 |
| `metadata_json` | `object` | 默认空对象 |

同一会话的参与者 ID 必须唯一，且最多一个参与者可明确标记为 profile owner。

### CanonicalMessage

| 字段 | 类型 | 规则 |
|---|---|---|
| `source_message_id` | `string` | 同一会话内唯一 |
| `sender_source_id` | `string` | 必须引用当前会话的参与者 |
| `timestamp` | aware datetime | 必须含偏移或时区 |
| `message_type` | enum | `text/image/file/audio/video/system/other` |
| `raw_content` | `string` | 原文原样保留 |
| `normalized_content` | `string` | 阶段 3 必须与 `raw_content` 完全相同 |
| `reply_to_source_message_id` | `string \| null` | 非空时必须引用同一会话的消息 |
| `source_order` | 非负整数 | 原始记录位置；跳过坏记录后不重编号 |
| `source_location` | `string \| null` | JSON Pointer、CSV 行号或文本行号 |
| `metadata_json` | `object` | 默认空对象；附件只保存结构化占位信息 |

`text` 正文去除空白后不得为空；其他消息类型允许空正文，以支持附件或系统占位。Parser 不读取真实附件。

### CanonicalConversation

字段为 `source_conversation_id`、`platform`、可选 `title`、可选 `started_at/ended_at`、`time_range_derived`、`participants`、`messages` 和 `metadata_json`。至少有一个参与者和一条有效消息。若时间范围缺失，则从有效消息最早和最晚时间推导，并设置 `time_range_derived=true`；结束时间不得早于开始时间。

Canonical 消息默认按 `(timestamp, source_order)` 升序输出。相同时间按 `source_order` 保持稳定顺序，原始位置不会丢失。Parser 不合并连续消息，也不把内容相同视为重复；只拒绝违反格式唯一性的重复 `source_message_id`。

### ParsedChatFile 与统计

`ParsedChatFile` 包含安全 basename `source_filename`、原始字节 `file_hash`、Parser 名称和版本、会话、警告及统计。绝不保存完整服务器路径。统计字段为 `conversation_count`、`participant_count`、`message_count`、`accepted_record_count`、`skipped_record_count` 和 `warning_count`；统计中不含正文。

## 4. ParserOptions 与失败模式

```text
error_mode: strict | lenient  # 默认 strict
default_timezone: IANA name | null
encoding: Python codec name  # 默认 UTF-8
```

`strict` 遇到第一条无效记录立即失败。`lenient` 只跳过可恢复的单条坏消息/CSV 行/文本行，同时保留原始 `source_order`，产生 warning 并增加跳过计数。文件不可读、哈希失败、整体 JSON/CSV/文本结构错误、跨行元数据冲突、无法确定格式、无有效会话、无有效消息或 Canonical 整体不一致始终失败。

编码不自动探测。默认接受 UTF-8 和 UTF-8 BOM；其他编码必须由调用方显式指定，且 Python 标准库必须支持。

## 5. 时间与时区

- 接受 ISO 8601/RFC 3339 aware datetime；`Z`/`z` 解释为 UTC。
- 带数字偏移的时间保留为 aware datetime，不依赖运行机器时区。
- naive datetime 只有在调用方显式提供有效 IANA `default_timezone` 时才可解释。
- 固定文本格式也可在文件头声明 IANA 时区；文件声明优先于选项。
- 不使用操作系统本地时区、文件修改时间或自然语言日期猜测。
- `tzdata` 是唯一新增运行依赖，因为 Windows 的 Python 标准库 `zoneinfo` 通常不自带 IANA 时区数据库。

## 6. 通用 JSON v1

完整结构示例见 `samples/synthetic/generic-chat.json`：

```json
{
  "format": "echomind-generic-chat",
  "version": "1.0",
  "platform": "generic",
  "conversations": [
    {
      "id": "conversation-1",
      "title": "Synthetic conversation",
      "platform": "generic",
      "started_at": null,
      "ended_at": null,
      "participants": [
        {
          "id": "person-a",
          "name": "Person A",
          "aliases": [],
          "is_profile_owner": true,
          "metadata_json": {}
        }
      ],
      "messages": [
        {
          "id": "message-1",
          "sender_id": "person-a",
          "timestamp": "2026-07-16T10:20:00+08:00",
          "type": "text",
          "content": "Synthetic message one",
          "reply_to_message_id": null,
          "metadata_json": {}
        }
      ],
      "metadata_json": {}
    }
  ]
}
```

顶层四个字段全部必填且不允许未知字段。会话必填 `id/participants/messages`；其余会话字段可选，省略的 `platform` 继承顶层值。参与者必填 `id/name`，其余字段可选。消息七个字段全部必填，其中 `reply_to_message_id` 可为 `null`。所有层级都拒绝未知字段，避免拼写错误被静默忽略。`format` 或版本不匹配时明确失败，不把任意 JSON 猜成此格式。消息级 Schema 错误可在 lenient 模式跳过，顶层或会话整体结构错误不可恢复。

## 7. 通用 CSV v1

表头必须按以下顺序完整一致；缺少、多出或重排均整体失败：

```text
conversation_id,conversation_title,platform,message_id,sender_id,sender_name,is_profile_owner,timestamp,message_type,content,reply_to_message_id
```

每个物理记录代表一条消息。`conversation_id/platform/message_id/sender_id/sender_name/timestamp/message_type` 必须非空；`conversation_title/content/reply_to_message_id` 可为空，但 text 类型的 content 仍不得只含空白。`is_profile_owner` 只能是小写/大小写等价的 `true`、`false` 或空值。相同会话 ID 聚合；相同发送者 ID 聚合。会话标题、平台或发送者属性冲突时整体失败，不静默覆盖。标准 CSV 引号、多行正文、UTF-8 BOM 均支持，错误位置使用物理 CSV 行号。

## 8. 固定纯文本 v1

```text
# conversation: conversation-1
# title: Synthetic conversation
# platform: generic
# timezone: Asia/Shanghai
# participant: person-a|Person A|owner
# participant: person-b|Person B|other
[message-1][2026-07-16 10:20:00] <person-a> Synthetic message one
[message-2][2026-07-16 10:21:00] <person-b> Synthetic message two
```

`conversation` 与 `platform` 头必填且只能出现一次；`title` 可选；`timezone` 可省略，但此时调用方必须显式传入 `default_timezone`。至少一个 `participant` 声明，格式固定为 `id|name|owner` 或 `id|name|other`，且必须位于消息之前。以 `##` 开头的整行是注释，空行忽略。消息格式固定为 `[message-id][timestamp] <participant-id> content`。当前文本格式不支持回复、附件 metadata 或续行；不会伪造这些关系，也不会尝试解析其他自然语言聊天格式。

## 9. WeFlow 边界

`WeFlowParser` 的 `available=false`，`can_parse` 始终为 false，避免仅凭 `.json` 误识别。显式调用时返回 `sample_required`。只有获得用户授权且彻底脱敏的真实导出样本、记录字段映射决策并补齐契约测试后，才会实现真实适配。

## 10. 错误、隐私与哈希

`ParserError` 字段为 `error_code`、安全 `safe_filename`、用户可理解的 `message`、可选 `parser_name/location`、`recoverable` 和只含安全结构信息的 `details`。异常不包含正文、完整文件、环境变量、密钥、本机绝对路径或不受控 traceback。阶段 3 Parser 不写日志。

SHA-256 对未经解码或规范化的原始文件字节计算，以 64 KiB 分块读取；它不负责数据库查重。文件正文虽然在解析时按所选编码读取，但不会进入错误或统计。

## 11. 当前限制

- 没有文件上传 API、目录扫描、压缩包支持、数据库写入或重复文件查询。
- 没有 Cleaner、连续消息合并、脱敏、附件读取或编码自动探测。
- 文件大小、消息数量和正文长度的上传安全上限留到阶段 5；当前哈希和 CSV 有基本大文件行为测试。
- 不支持真实 WeFlow，也不自动兼容任何第三方 JSON/CSV/文本导出。
