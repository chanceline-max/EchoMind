# EchoMind 导入格式规范

## 1. Parser 契约

每个 Parser 实现统一协议：

```python
class Parser(Protocol):
    name: str
    version: str

    def can_parse(self, file: ImportFile) -> ParseMatch: ...
    def parse(self, file: ImportFile) -> ParsedImport: ...
    def validate(self, result: ParsedImport) -> ValidationReport: ...
```

- `can_parse` 返回置信等级和理由，不只返回布尔值。
- `parse` 不写数据库，输出规范中间对象。
- `validate` 返回错误/警告及安全位置，不抛弃全部可用记录。
- Parser 不记录正文、不执行文件内容、不访问网络。

## 2. 规范化消息

```json
{
  "source_message_id": "original-id",
  "conversation_id": "conversation-id",
  "sender": {
    "name": "张三",
    "is_profile_owner": true
  },
  "timestamp": "2026-07-16T10:20:00+08:00",
  "message_type": "text",
  "raw_content": "原始内容",
  "normalized_content": "清洗后的内容",
  "reply_to": null,
  "metadata": {}
}
```

Parser 只负责尽可能保真地转换到 canonical 层；`normalized_content` 的深度清洗由 Cleaning Pipeline 完成。

## 3. 通用 JSON v1

推荐顶层结构：

```json
{
  "schema_version": "echomind-import-1.0",
  "platform": "generic",
  "profile_owner": "我",
  "conversations": [
    {
      "id": "conversation-1",
      "title": "示例会话",
      "participants": ["我", "朋友"],
      "messages": [
        {
          "id": "message-1",
          "sender": "我",
          "timestamp": "2026-07-16T10:20:00+08:00",
          "type": "text",
          "content": "这是合成示例，不是真实聊天。",
          "reply_to": null
        }
      ]
    }
  ]
}
```

必须字段：conversation id、message sender、content。timestamp 可缺失但产生警告；缺失 message id 时生成确定性 ID。

## 4. 通用 CSV v1

UTF-8 CSV 表头：

```text
conversation_id,conversation_title,message_id,sender,timestamp,message_type,content,reply_to
```

- `conversation_id`、`sender`、`content` 必填。
- 多行 content 必须符合标准 CSV 引号规则。
- timestamp 使用 ISO 8601；解析失败保留 raw 值并报告警告。
- 文件导入不会执行公式，但未来 CSV 导出必须防止公式注入。

## 5. 纯文本 v1

MVP 支持明确、可验证的行格式：

```text
[2026-07-16 10:20:00 +08:00] 我: 这是第一条消息
[2026-07-16 10:21:00 +08:00] 朋友: 这是第二条消息
```

- 时间、发送者、正文由方括号和第一个 `: ` 分隔。
- 连续缩进行可作为上一条消息的续行。
- 不符合格式的行返回行号警告；不猜测复杂自然语言日期。
- 其他常见纯文本格式后续以独立 Parser 添加，不在一个 Parser 中堆叠模糊正则。

## 6. WeFlow 适配器

当前没有真实、授权、脱敏的 WeFlow 导出样本，因此不声称完整支持。MVP 只提供：

- `WeFlowParser` 接口框架和检测钩子。
- 基于合成结构的契约测试。
- `samples/README.md` 中的样本提交与脱敏要求。
- 收到真实样本后记录 parser version 和字段映射决策。

## 7. 错误模型

错误包括：unsupported_format、encoding_error、invalid_structure、missing_required_field、invalid_timestamp、duplicate_message、size_limit_exceeded、unsafe_path、internal_parser_error。

对用户返回文件名、会话/行/记录位置和修复建议；日志只记录错误代码、计数和 job ID，不记录出错正文。

## 8. 编码与限制

- 优先接受 UTF-8/UTF-8 BOM；其他编码通过检测步骤转换并记录置信度。
- 原始字节 hash 在任何转换前计算。
- 文件大小、消息数量、单条正文长度上限在阶段 3/5 通过样本、性能和上传安全测试确定，并写入配置及 UI。
- MVP 默认拒绝压缩包，避免路径穿越和压缩炸弹风险。
