# 蛇蛇争霸 监控与日常任务脚本

## 功能

- **好友状态监控** (`sszb_monitor.py`)：监控好友在线/离线状态，统计每日自由战局数，状态变更时推送通知。
- **每日任务** (`daily_tasks.py`)：每日签到、摇钱树、免费扭蛋、免费圣衣商城。
- **认证管理** (`auth_manager.py`)：登录凭证被服务器销毁后，`authKey` 过期错误(-73)，能利用 `openKey` 重新登录。

## 配置 (config.json)

复制 `config.example.json` 为 `config.json`，填入抓包获取的参数。

---

## 抓包教程

使用前必须通过抓包获取登录凭据。蛇蛇争霸是 PC 端游戏 (`snake.exe`)，以下介绍 Windows 环境下的抓包方法。

### 方法一：Proxifier + 代理工具

#### 准备工作

游戏不走系统代理，使用 Proxifier 强制指向代理：

1. 下载安装 [Fiddler Classic](https://www.telerik.com/fiddler/fiddler-classic)
2. 安装 [Proxifier](https://www.proxifier.com/)
3. 启动 Fiddler，默认监听 `127.0.0.1:8888`
4. 启动 Proxifier，配置代理服务器指向 Fiddler (`127.0.0.1:8888`)
6. 添加规则：应用程序 `snake.exe` → 通过代理

~~#### 配置系统代理~~

~~Fiddler 启动后会自动设置系统代理。如未生效：~~
~~- 设置 → 网络和 Internet → 代理 → 手动设置~~
~~- 地址：`127.0.0.1`，端口：`8888`~~

#### 抓取流量

1. 启动蛇蛇争霸，登录游戏
2. 在 Fiddler 左侧列表筛选：
   - 按 Host 筛选：`snake-pc-norm-dyn.gz.1252595457.clb.myqcloud.com`
   - 或按 URL 搜索：`snake_require`
3. 找到 `msg_id=30001` 的 POST 登录请求

#### 查看请求内容

1. 点击目标请求
2. 右侧面板选择 `Inspectors` → `Raw` 或 `WebForms`
3. 查看 Request Body 中的 `msg` 字段（需要 URL 解码）

### 方法二：Wireshark

#### 准备工作

1. 下载安装 [Wireshark](https://www.wireshark.org/)
2. 选择正在使用的网卡开始抓包

#### 抓取流量

1. 启动 Wireshark，选择网卡
2. 设置过滤器：`http.host contains "snake-pc-norm-dyn"`
3. 启动蛇蛇争霸，登录游戏
4. 在 Wireshark 中找到 HTTP POST 请求

#### 查看请求内容

1. 右键点击目标数据包 → Follow → HTTP Stream
2. 查看完整的 HTTP 请求和响应

---

## 请求示例

**登录请求 (msg_id=30001)：**

```http
POST /zgame/?m=snake&a=snake_require HTTP/1.1
Host: snake-pc-norm-dyn.gz.1252595457.clb.myqcloud.com
User-Agent: UnityPlayer/2017.4.25f1 (UnityWebRequest/1.0, libcurl/7.51.0-DEV)
Accept: */*
Accept-Encoding: identity
Content-Type: application/x-www-form-urlencoded
X-Unity-Version: 2017.4.25f1

msg_id=30001&msg={"openID":"79C08456AB664267ED5660282496C***","openKey":"3A62DB26D046E5299B430371F4D297C4","pfID":2,"version":"8.9.7","lastLoginTimeStamp":1770021088,"sign":"d26ad73194da041c68048f30ad81ff**","bundleIdentifier":"com.bairimeng.snake.13","deviceID":"b227a7c94278f2e9de046915c1d01c2f89dee3**","idfv":""}
```

**响应：**

```json
{
    "serverTimeStamp": 1770380210,
    "roleID": 34011692,
    "openID": "79C08456AB664267ED5660282496CF**",
    "authKey": "ce0f916c4a1637c892470802968e58**",
    "accountName": "቉቉",
    "lastLoginTimeStamp": 1770021088,
    "sign": "d26ad73194da041c68048f30ad81ff**",
    "audit": 1,
    "errorCode": 0
}
```

**注意**：`msg` 字段是 URL 编码的，在 Fiddler 中选择 `WebForms` 视图或使用在线工具解码。

---

## 参数说明

### 从请求 `msg` 字段提取（填入 `accounts` 数组）

| 参数 | 说明 | 来源 |
|---|---|---|
| `openID` | 账号唯一标识 | 请求 `msg` |
| `openKey`, `sign` | qq大厅登录凭证、签名，用于自动刷新游戏 `authKey` | 请求 `msg` |
| `lastLoginTimeStamp` | 上次登录时间戳 | 请求 `msg` |
| `roleID` | 角色 ID | 响应 |
| `authKey` | 游戏登录凭证 (经常需要刷新) | 响应 |
| `accountName` | 角色名 (可选) | 响应 |

### 公共参数（填入 `common` 对象）

| 参数 | 说明 |
|---|---|
| `pfID` | 平台 ID |
| `version` | 游戏版本 |
| `bundleIdentifier` | 包名 |
| `deviceID` | 设备 ID |

### 监控目标（`targets` 数组，可选）

用于 `sszb_monitor.py` 监控指定好友。

| 参数 | 说明 |
|---|---|
| `id` | 目标角色 ID |
| `name` | 备注名 |

---

## 运行

```bash
pip install -r requirements.txt
python sszb_monitor.py   # 监控目标
python daily_tasks.py    # 每日任务
```

## 注意

- `openKey` 有时效性，失效需重新抓包。
- 仅供学习交流。
