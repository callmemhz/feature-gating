# 使用指南

## 基本概念

### Project（项目）

项目是功能项的容器，用于组织和管理相关的功能开关。

### Item（功能项）

每个功能项代表一个可以被控制的功能点，包含：
- **Key**: 唯一标识符
- **Description**: 功能描述
- **Enabled**: 总开关
- **Condition Groups**: 条件组列表（推荐使用，支持 AND/OR 逻辑）
- **Conditions**: 灰度条件列表（旧版，仅 AND 逻辑，向后兼容）

### Condition Group（条件组）

条件组支持更灵活的逻辑组合：
- **组间逻辑**：OR（任一组满足即可）
- **组内逻辑**：可配置 AND 或 OR

示例结构：
```json
{
  "condition_groups": [
    {
      "logic": "and",
      "conditions": [...]
    },
    {
      "logic": "or",
      "conditions": [...]
    }
  ]
}
```

评估逻辑：`(组1的结果) OR (组2的结果) OR ...`

### Condition（条件）

条件用于定义灰度规则，格式为：

```
hash(field) operator value comparator target
```

例如：`hash(user_id) % 10 < 2` 表示向 20% 的用户开放。

## Web 界面使用

### 1. 登录系统

访问 http://localhost:8000/login，使用管理员账户登录。

### 2. 创建项目

1. 在左侧导航栏点击 "+" 按钮
2. 输入项目名称
3. 点击"创建"

### 3. 添加功能项

1. 在左侧选择一个项目
2. 点击右上角"新增 Item"按钮
3. 填写信息：
   - Key: 功能的唯一标识（如 `new_chat_ui`）
   - 描述: 功能说明
   - 启用状态: 打开或关闭
   - 条件: 点击"添加"按钮添加灰度条件

### 4. 配置灰度条件

每个条件包含 5 个部分：

| 参数 | 说明 | 示例 |
|------|------|------|
| field | 业务字段 | user_id, chat_id, email, org_id |
| operator | 运算符 | %, /, //, * |
| value | 运算值 | 10 |
| comparator | 比较符 | >, <, >=, <=, ==, != |
| target | 目标值 | 2 |

#### 常见灰度场景

**场景 1: 向 20% 用户开放**

```
field: user_id
operator: %
value: 10
comparator: <
target: 2
```

计算：`hash(user_id) % 10 < 2`

**场景 2: 向 50% 用户开放**

```
field: user_id
operator: %
value: 10
comparator: <
target: 5
```

计算：`hash(user_id) % 10 < 5`

**场景 3: 向特定范围用户开放**

```
field: user_id
operator: %
value: 100
comparator: >=
target: 20

field: user_id
operator: %
value: 100
comparator: <
target: 30
```

计算：`20 <= hash(user_id) % 100 < 30`（10% 用户）

**场景 4: 白名单用户 OR 灰度比例（使用条件组）**

希望白名单用户始终可以访问，同时对非白名单用户进行 20% 灰度：

```json
{
  "condition_groups": [
    {
      "logic": "and",
      "conditions": [
        {"field": "user_id", "operator": "in", "value": "vip_user1\nvip_user2\nvip_user3"}
      ]
    },
    {
      "logic": "and",
      "conditions": [
        {"field": "user_id", "operator": "%", "value": 100, "comparator": "<", "target": 20}
      ]
    }
  ]
}
```

计算：`(user_id in 白名单) OR (hash(user_id) % 100 < 20)`

**场景 5: 复杂条件组合（多条件组内 AND）**

仅对特定邮箱后缀且命中灰度的用户开放：

```json
{
  "condition_groups": [
    {
      "logic": "and",
      "conditions": [
        {"field": "email", "operator": "in", "value": "@company.com\n@partner.com"},
        {"field": "user_id", "operator": "%", "value": 100, "comparator": "<", "target": 50}
      ]
    }
  ]
}
```

计算：`(email 包含 @company.com 或 @partner.com) AND (命中 50% 灰度)`

### 5. 保存配置

1. 配置完成后，点击右侧边栏的"保存更改"
2. 可选填写备注说明本次修改
3. 系统会自动创建配置快照

### 6. 查看历史记录

在右侧边栏可以看到历史修改记录：
- 修改者
- 修改时间
- 备注
- 点击"查看"可以看到当时的配置快照

## API 使用

### 查询功能是否启用

#### GET 请求

```bash
curl "http://localhost:8000/api/fg/check?project=main&key=new_chat_ui&user_id=550e8400-e29b-41d4-a716-446655440000"
```

#### POST 请求

```bash
curl -X POST "http://localhost:8000/api/fg/check" \
  -H "Content-Type: application/json" \
  -d '{
    "project": "main",
    "key": "new_chat_ui",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "chat_id": "chat_123"
  }'
```

#### 响应

```json
{
  "enabled": true,
  "key": "new_chat_ui"
}
```

### 在业务代码中使用

#### Python 示例

```python
import requests

def check_feature(project, key, user_id):
    """检查功能是否启用"""
    response = requests.get(
        "http://localhost:8000/api/fg/check",
        params={
            "project": project,
            "key": key,
            "user_id": user_id
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        return data["enabled"]
    return False

# 使用示例
if check_feature("main", "new_chat_ui", user_id):
    # 启用新功能
    show_new_chat_ui()
else:
    # 使用旧功能
    show_old_chat_ui()
```

#### JavaScript 示例

```javascript
async function checkFeature(project, key, userId) {
  const response = await fetch(
    `http://localhost:8000/api/fg/check?project=${project}&key=${key}&user_id=${userId}`
  );
  
  if (response.ok) {
    const data = await response.json();
    return data.enabled;
  }
  return false;
}

// 使用示例
if (await checkFeature('main', 'new_chat_ui', userId)) {
  showNewChatUI();
} else {
  showOldChatUI();
}
```

## 管理员功能

访问 http://localhost:8000/admin 可以管理用户。

### 添加用户

1. 填写用户名和密码
2. 选择角色（普通用户 / 管理员）
3. 点击"添加用户"

### 修改密码

点击用户列表中的"修改密码"按钮。

### 删除用户

点击用户列表中的"删除"按钮（不能删除自己）。

## 最佳实践

### 1. 灰度策略

**渐进式灰度**：

1. 第一阶段：5% 用户（`% 100 < 5`）
2. 第二阶段：20% 用户（`% 10 < 2`）
3. 第三阶段：50% 用户（`% 10 < 5`）
4. 第四阶段：100% 用户（删除条件或直接 enabled）

### 2. 命名规范

**项目命名**：
- 使用小写字母和下划线
- 例如：`main`, `user_center`, `chat_service`

**Key 命名**：
- 使用描述性名称
- 例如：`new_chat_ui`, `advanced_search`, `ai_assistant`

### 3. 安全建议

1. **修改默认密码**：首次登录后立即修改管理员密码
2. **最小权限原则**：只给必要的用户管理员权限
3. **保护 API**：在生产环境中考虑添加 API Key 认证
4. **定期备份**：定期备份 MongoDB 数据

### 4. 性能优化

1. **合理设置缓存时间**：根据配置更新频率调整 `CACHE_TTL_SECONDS`
2. **批量查询**：如需检查多个功能，考虑批量 API
3. **监控缓存命中率**：确保缓存有效工作

## 故障排查

### 问题 1: 配置不生效

**检查清单**：
1. 是否点击了"保存更改"
2. 缓存是否已过期（等待 60 秒或重启服务）
3. Item 的 enabled 开关是否打开
4. 条件表达式是否正确

### 问题 2: 灰度比例不符合预期

**原因**：
- 哈希分布不均匀是正常的，尤其在样本量小时
- 建议使用较大的样本量测试

**验证方法**：
```python
# 测试 10000 个用户的灰度分布
from app.services.hash import hash_user_id

count = 0
for i in range(10000):
    user_id = f"user_{i}"
    if hash_user_id(user_id) % 10 < 2:
        count += 1

print(f"灰度比例: {count/10000*100}%")  # 应接近 20%
```

### 问题 3: 无法登录

**检查**：
1. 用户名密码是否正确
2. MongoDB 是否正常运行
3. 查看应用日志

## 监控和日志

### 查看应用日志

```bash
# 如果使用 uvicorn --reload
# 日志会输出到终端

# 如果使用 systemd
sudo journalctl -u wawa-fg -f
```

### 监控 MongoDB

```bash
# 连接到 MongoDB
mongosh wawa-fg

# 查看集合统计
db.items.countDocuments()
db.users.countDocuments()
db.snapshots.countDocuments()
```

### 性能监控

建议监控以下指标：
- API 响应时间
- 缓存命中率
- MongoDB 查询性能
- 并发请求数

