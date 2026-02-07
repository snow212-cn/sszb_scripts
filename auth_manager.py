"""
auth_manager.py - 通用认证管理模块

提供:
- 配置文件的加载和保存
- 登录函数 (自动刷新 authKey)
- 通用请求函数 (支持 -73 错误自动重试)
- 异常通知机制
"""

import requests, json, datetime, os, urllib.parse, sys

# ================= 配置区域 =================
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')
BASE_URL = "http://snake-pc-norm-dyn.gz.1252595457.clb.myqcloud.com/zgame/?m=snake&a=snake_require"
HEADERS = {
    "Host": "snake-pc-norm-dyn.gz.1252595457.clb.myqcloud.com",
    "User-Agent": "UnityPlayer/2017.4.25f1 (UnityWebRequest/1.0, libcurl/7.51.0-DEV)",
    "Accept": "*/*",
    "Accept-Encoding": "identity",
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Unity-Version": "2017.4.25f1"
}

# 配置缓存
_CONFIG_CACHE = None

class FatalAuthError(Exception):
    """严重认证错误，无法恢复，需要跳过当前账号"""
    pass

# ================= 通知功能 =================
def send_notification(title, content):
    """通过青龙面板发送通知，如果不可用则打印"""
    print(f"正在发送通知: {title}", end=' ')
    try:
        # 尝试访问全局注入的 QLAPI (青龙环境)
        # if 'QLAPI' in globals():
            print(QLAPI.systemNotify({"title": title, "content": content}))
            return
        
    except Exception as e:
        # 尝试访问 builtins 中的 QLAPI
        import builtins
        if hasattr(builtins, 'QLAPI'):
            print(builtins.QLAPI.systemNotify({"title": title, "content": content}))
            return
        print(f"尝试发送通知失败: {e}")
    
    # 默认回退：打印到控制台
    print(f"\n[NOTIFICATION] {title}\n{content}\n")

# ================= 配置管理 =================
def load_config():
    """加载配置文件，返回配置字典并缓存"""
    global _CONFIG_CACHE
    if not os.path.exists(CONFIG_FILE):
        print(f"错误: 配置文件未找到 {CONFIG_FILE}")
        return None
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            _CONFIG_CACHE = json.load(f)
            return _CONFIG_CACHE
    except Exception as e:
        print(f"错误: 读取配置文件失败 {e}")
        return None

def save_config():
    """保存当前缓存的配置到文件"""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        return
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(_CONFIG_CACHE, f, ensure_ascii=False, indent=2)
        print("配置文件已保存。")
    except Exception as e:
        print(f"错误: 保存配置文件失败 {e}")

def get_config_cache():
    """获取配置缓存的引用"""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        load_config()
    return _CONFIG_CACHE

def get_common_param(key, default=None):
    """从配置文件的 common 节点获取公共参数"""
    config = get_config_cache()
    if config and "common" in config:
        return config["common"].get(key, default)
    return default

# ================= 登录功能 =================
def login(account):
    """
    登录函数：使用 openID 等凭据获取新的 authKey 并更新配置文件
    
    Args:
        account: 配置文件中的账号字典 (引用传递，会直接修改)
    
    Returns:
        bool: 登录是否成功
    """
    print(f"[{account.get('note', '未知账号')}] 正在尝试登录以刷新认证状态...")
    msg_id = 30001
    msg_data = {
        "openID": account.get("openID", ""),
        "openKey": account.get("openKey", ""),
        "pfID": get_common_param("pfID", 2),
        "version": get_common_param("version", "8.9.7"),
        "lastLoginTimeStamp": account.get("lastLoginTimeStamp", 0),
        "sign": account.get("sign", ""),
        "bundleIdentifier": get_common_param("bundleIdentifier", "com.bairimeng.snake.13"),
        "deviceID": get_common_param("deviceID", "b227a7c94278f2e9de046915c1d01c2f89dee3ba"),
        "idfv": ""
    }
    
    msg_json = json.dumps(msg_data, ensure_ascii=False)
    encoded_msg = urllib.parse.quote(msg_json)
    body = f"msg_id={msg_id}&msg={encoded_msg}"
    
    try:
        response = requests.post(BASE_URL, headers=HEADERS, data=body, timeout=15)
        res = response.json() if response.status_code == 200 else None
        
        if res and res.get("errorCode") == 0:
            print(f"登录成功: {res.get('accountName')} (RoleID: {res.get('roleID')})")
            account["authKey"] = res.get("authKey")
            account["roleID"] = str(res.get("roleID"))
            account["accountName"] = res.get("accountName")
            save_config()  # 立即持久化重要认证参数
            return True
        else:
            error_msg = res.get('errorMsg', 'HTTP错误或解析失败') if res else 'HTTP错误'
            print(f"登录失败: {error_msg}")
            return False
    except Exception as e:
        print(f"登录异常: {e}")
        return False

# ================= 通用请求 =================
def make_request(msg_id, msg_data, account, retry_on_auth_fail=True):
    """
    通用请求函数：支持 authKey 失效时自动调用 login 并重试
    如果自动登录也失败，将发送通知并抛出 FatalAuthError。
    
    Args:
        msg_id: 消息ID
        msg_data: 消息体字典
        account: 账号配置字典
        retry_on_auth_fail: 是否在遇到 -73 错误时自动重试
    
    Returns:
        dict | None: 服务器响应的 JSON 字典，或 None（请求失败但非致命错误）
        
    Raises:
        FatalAuthError: 当自动登录失败，无法恢复时抛出
    """
    msg_json = json.dumps(msg_data, ensure_ascii=False)
    encoded_msg = urllib.parse.quote(msg_json)
    body = f"msg_id={msg_id}&msg={encoded_msg}"
    note = account.get('note', '未知账号')
    roleID = account.get('roleID', 'unknown_id')
    auth_failed_mark_file = os.path.join(os.path.dirname(__file__), f'.auth_failed_mark_{roleID}')
    
    try:
        response = requests.post(BASE_URL, headers=HEADERS, data=body, timeout=15)
        if response.status_code != 200:
            print(f"请求失败: HTTP {response.status_code}")
            return None
        
        res = response.json()
        
        # 处理认证失败 (-73)
        if res.get("errorCode") == -73 and retry_on_auth_fail:
            # 检查失败静默标记，若存在则跳过登录尝试，抛出致命错误
            if os.path.exists(auth_failed_mark_file):
                # err_msg = f"账号 [{note}] 此前已登录失败，跳过重试并停止执行后续！"
                err_msg = f"[{note}] 此前已认证失败，处于静默模式。\n该账号后续任务已停止，请尽快手动重新抓包更新配置！"
                print(f"[CRITICAL] {err_msg}")
                raise FatalAuthError(err_msg)

            print(f"账号:[{note}] 认证过期(-73)！发送通知并尝试自动登录...")
            send_notification(f"蛇蛇争霸 - 账号认证失败", f"账号 [{note}] 认证已过期 (-73)，尝试重新登录...")
            
            if login(account): # 自动重新登录成功，更新请求数据中的 authKey 和 roleID 后重试
                msg_data["authKey"] = account["authKey"]
                # if "roleID" in msg_data:
                #     msg_data["roleID"] = int(account["roleID"])
                return make_request(msg_id, msg_data, account, retry_on_auth_fail=False)
            else: # 自动登录失败，这是严重错误，必须推送通知人来解决
                err_msg = f"账号 [{note}] 自动登录失败，无法更新authKey！\n可能原因: openKey过期或网络问题。\n该账号后续任务将停止，请尽快手动重新抓包更新配置！"
                print(f"[CRITICAL] {err_msg}")
                if not os.path.exists(auth_failed_mark_file): # 认证首次出错，发送通知并创建静默标记
                    # msg = f"检测到关键错误 -73：账号认证失败 (authKey过期或在别处登录)。\n账号: {account_note}\n后续将停止通知直至恢复正常，请及时重新登录，抓包，更新authKey！"
                    send_notification("蛇蛇争霸 - 账号认证失败", err_msg)
                    try:
                        with open(auth_failed_mark_file, 'w', encoding='utf-8') as f:
                            f.write(f"Auth failed at: {datetime.datetime.now().isoformat()}")
                    except Exception as e:
                        print(f"创建静默标记失败: {e}")
                            
                raise FatalAuthError(err_msg)

        # 如果请求成功 (0)，清除可能存在的失败标记 (针对非-73但偶尔恢复的情况，或重试成功的情况)
        if res.get("errorCode")==0 and os.path.exists(auth_failed_mark_file):
            os.remove(auth_failed_mark_file)
            msg = f"账号 [{note}] 请求成功，已清除静默失败标记。"
            print(msg)
            send_notification(f"蛇蛇争霸 - 账号 [{note}] 认证恢复正常", msg)
        return res
    except FatalAuthError:
        raise FatalAuthError
    except Exception as e:
        print(f"请求异常: {e}")
        return None

def get_base_msg(account):
    """构建基础消息体，包含 authKey 等必填项"""
    return {
        "authKey": account.get("authKey"),
        "accountName": account.get("accountName", ""),
        "roleID": int(account.get("roleID", 0)),
        "pfID": get_common_param("pfID", 2),
        "deviceID": get_common_param("deviceID", "b227a7c94278f2e9de046915c1d01c2f89dee3ba"),
        "bundleIdentifier": get_common_param("bundleIdentifier", "com.bairimeng.snake.13"),
        "version": get_common_param("version", "8.9.7")
    }
