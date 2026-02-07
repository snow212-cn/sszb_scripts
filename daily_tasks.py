"""
daily_tasks.py - 每日任务脚本

功能:
- 每日签到
- 摇钱树
- 三次免费扭蛋 (间隔约5分钟)
"""

import time
from auth_manager import load_config, make_request, get_base_msg, FatalAuthError

def daily_sign_in(account):
    """每日签到任务"""
    print(f"[{account.get('note')}] 检查每日签到...")
    msg_data_base = get_base_msg(account)
    
    # 1. 打开界面检查状态 (31010)
    info = make_request(31010, msg_data_base, account)
    if not info or info.get("errCode") != 0:
        print(f"获取签到信息失败: {info}")
        return

    sign_day = info.get("signDay", 0)
    status = info.get("status", [])
    
    # 判断当前天数是否可领 (1表示可领)
    if 0 < sign_day <= len(status) and status[sign_day-1] == 1:
        print(f"发现第 {sign_day} 天未签到，正在执行签到...")
        sign_data = msg_data_base.copy()
        sign_data.update({"type": 0, "day": sign_day})
        res = make_request(31011, sign_data, account)
        if res and res.get("errCode") == 0:
            print(f"签到成功！获得奖励: {res.get('awards')}")
        else:
            print(f"签到失败: {res}")
    else:
        print(f"今日 (第{sign_day}天) 不满足签到条件或已签到。状态: {status[sign_day-1] if 0 < sign_day <= len(status) else '未知'}")

    # 2. 周日领金币奖励 (31012)
    if info.get("weekendStatus") == 1:
        time.sleep(1)
        print("发现周日金币奖励可领取，正在领取...")
        res = make_request(31012, msg_data_base, account)
        if res and res.get("errCode") == 0:
            print(f"周日奖励领取成功！获得: {res.get('awards')}")
        else:
            print(f"周日奖励领取失败: {res}")

def shake_tree(account):
    """摇钱树任务"""
    print(f"[{account.get('note')}] 检查摇钱树...")
    msg_data_base = get_base_msg(account)

    # 1. 打开界面
    info = make_request(30685, msg_data_base, account)
    if info and info.get("oncePrice") == 0 and info.get("residueTimes", 0) > 0:
        print(f"发现免费机会剩余次数: {info.get('residueTimes')}")
        shake_data = msg_data_base.copy()
        shake_data.update({"count": 1})
        res = make_request(30686, shake_data, account)
        if res:
            print(f"摇树成功: {res.get('items')}")
    else:
        print("今日免费摇树已用完或不满足条件。")

def cloth_shop_buy(account):
    """圣衣商城每日免费购买"""
    print(f"[{account.get('note')}] 检查圣衣商城免费礼包...")
    msg_data_base = get_base_msg(account)
    
    # 1. 查看界面 (30843)
    info = make_request(30843, msg_data_base, account)
    if not info or "infos" not in info:
        print(f"获取圣衣商城信息失败: {info}")
        return

    # 2. 寻找价格为0且未购买过的项
    target_gift = None
    for item in info["infos"]:
        if item.get("realPrice") == 0 and (item.get("boughtCount") is None or item.get("boughtCount") < item.get("totalCount", 1)):
            target_gift = item
            break
    
    if target_gift:
        gift_id = target_gift.get("clothGiftID")
        print(f"发现免费礼包: {gift_id}，正在购买...")
        buy_data = msg_data_base.copy()
        buy_data.update({"clothGiftID": gift_id, "buyCount": 1})
        res = make_request(30844, buy_data, account)
        if res and "items" in res:
            print(f"购买成功！获得奖励: {res.get('items')}")
        else:
            print(f"购买失败: {res}")
    else:
        print("今日没有可领取的免费礼包。")

def lucky_draw(account):
    """免费扭蛋任务 (每天3次, 间隔5分钟)"""
    print(f"[{account.get('note')}] 检查扭蛋任务...")
    msg_data_base = get_base_msg(account)

    for i in range(3):
        print(f"--- 尝试第 {i+1} 次扭蛋 ---")
        info = make_request(30250, msg_data_base, account)
        if not info or "infos" not in info:
            print("获取扭蛋信息失败")
            break
            
        gacha_info = info["infos"][0]
        free_count = gacha_info.get("coinFreeReaminCount", 0)
        next_free_time = gacha_info.get("coinFreeTime", 0)
        now = int(time.time())

        if free_count > 0:
            print(f'免费机会剩余次数: {free_count}')
            wait_time = next_free_time - now
            if wait_time > 0:
                print(f"免费冷却中，还需等待 {wait_time} 秒...")
                if i < 2: 
                    time.sleep(wait_time + 3)
                    continue
                else:
                    break
            
            draw_data = msg_data_base.copy()
            draw_data.update({"isActivity": 0, "luckyToyID": 1, "drawType": 5})
            res = make_request(30251, draw_data, account)
            if res and res.get("errorCode") == 0:
                print(f"扭蛋成功！获得: {res.get('items')}")
                if i < 2 and free_count > 1:
                    print("等待5分钟后进行下一次...")
                    time.sleep(301)
            else:
                break
        else:
            print("今日免费扭蛋已用完。")
            break

def main():
    config = load_config()
    if not config:
        return

    for account in config.get("accounts", []):
        print(f"\n>>>> 开始处理账号: {account.get('note')} <<<<")
        
        try:
            # 依次执行各项任务
            daily_sign_in(account)
            time.sleep(1)
            shake_tree(account)
            time.sleep(1)
            cloth_shop_buy(account)
            time.sleep(1)
            lucky_draw(account)
            
        except FatalAuthError:
            print(f"!!!! 账号 {account.get('note')} 遭遇严重认证错误，已跳过剩余任务 !!!!")
            continue
        except Exception as e:
            print(f"账号 {account.get('note')} 执行任务时发生未知错误: {e}")
            continue

if __name__ == "__main__":
    main()
