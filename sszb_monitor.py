"""
sszb_monitor.py - 蛇蛇争霸监控脚本

功能:
- 监控好友在线状态
- 统计自由战局数
- 状态变更通知
"""

import json, time, os, datetime, sys, io, csv

# 导入通用认证模块
from auth_manager import load_config, save_config, login, get_base_msg, get_common_param, make_request, BASE_URL, HEADERS, FatalAuthError

# 添加上一级目录到 sys.path 以便导入 notify.py
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
except:
    pass

# ================= 配置区域 =================
# 在提供的样本中所有人status都是0(离线)。游戏中是 2，在线是1，请自行设置！
# 自由战对应的 gameMode 数值。-1是无模式/离线，"1"是团战，"0"是自由战。
FREE_BATTLE_MODE_ID = 0

def send_notification(title, content):
    """通过青龙面板发送通知"""
    try:
        # if 'QLAPI' in globals():
            print(f"正在发送通知: {title}")
            print(QLAPI.systemNotify({"title": title, "content": content}))
        # else:
            # 如果本地环境没有 QLAPI，也可以调用 auth_manager 的 send_notification，或者简单打印
    except Exception as e:
        print(f"发送通知失败: {e}")
        print(f"\n[NOTIFICATION] {title}\n{content}\n")

def check_response(data, account):
    """
    检查接口响应是否存在错误
    注意: -73 错误会在 make_request 中自动处理, 这里只处理其他情况
    """
    if not isinstance(data, dict):
        print(f"[{account.get('note')}] 接口返回异常: 非字典格式")
        return False
    
    err_code = data.get('errorCode', 0)
    
    if err_code != 0:
        err_msg = data.get('errorMsg', '未知错误')
        print(f"[{account.get('note')}] 接口返回错误: [{err_code}] {err_msg}")
        return False
        
    return True

def view_target(target_id, account):
    """查看目标用户详细信息"""
    msg_data = get_base_msg(account)
    msg_data["requestRoleID"] = int(target_id)
    
    data = make_request(30002, msg_data, account)
    if not data or not check_response(data, account):
        return {}
    
    target_keys = ['publicInfo', 'gold', 'diamonds', 'killCount', 'maxContinueKill', 'championCount', 'historyScore',
                   'goldNum', 'silverNum', 'copperNum', 'bestOverall', 'bestOverallProbability', 'todaySpaceVisitorNum',
                   'teamplayWinningTimes', 'teamplayWinningProbability', 'teamplayBestTimes', 'teamplayBestProbability']
    return {k: data[k] for k in data if k in target_keys}

def get_state_now(account, followType=3, startID=1, endID=20):
    """
    获取关注列表/好友列表的状态
    
    Args:
        account: 账号配置字典
        followType: 关注类型. 3=好友, 1=关注列表
        startID: 起始位置
        endID: 结束位置

    Returns:
        dict: 关注列表所有角色
    """
    msg_data = get_base_msg(account)
    msg_data.update({
        "followType": followType,
        "startID": startID,
        "endID": endID,
        "onlineFirst": True
    })
    
    data = make_request(30014, msg_data, account)
    if not data or not check_response(data, account):
        return {}
    return data

def regroup(data):
    """重组json数据为以人为单位的列表"""
    if not data or 'roleID' not in data:
        return []
    clean_user_list = []
    for i in range(len(data['roleID'])):
        public_info = data['publicInfos'][i]
        space_status = data['spaceStatus'][i]
        user_obj = {
            "id": data['roleID'][i],
            "name": public_info['name'],
            "avatar_url": public_info['icon'],
            "location": public_info['area'],
            "basic_info": {"sex": int(public_info['sex']), "age": int(public_info['age']), "level": int(public_info['levelInfo']['level'])},
            "status": {"description": data['statusDesc'][i], "mood": space_status['newMood'], "is_top": bool(data['isTop'][i])}
        }
        clean_user_list.append(user_obj)
    return clean_user_list

def format_target_detail(detail):
    """格式化目标详情为易读的字符串"""
    if not detail:
        return "获取详细信息失败"
    
    res = []
    res.append(f"【今日目标情况】")
    res.append(f"- 今日空间访客: {detail.get('todaySpaceVisitorNum', 0)}")
    res.append(f"【对战汇总】")
    res.append(f"- 段位: {detail['publicInfo'].get('grade', 0)}")
    res.append(f"- 击杀总数: {detail.get('killCount', 0)}")
    res.append(f"- 最高连杀: {detail.get('maxContinueKill', 0)}")
    res.append(f"- 全场最佳数: {detail.get('bestOverall', 0)} (胜率: {detail.get('bestOverallProbability', 0)}%)")
    res.append(f"- 团战最佳数: {detail.get('teamplayBestTimes', 0)} (胜率: {detail.get('teamplayWinningProbability', 0)}%)")
    res.append(f"【账号资产】")
    res.append(f"- 金币: {detail.get('gold', 0)} | 钻石: {detail.get('diamonds', 0)}")
    res.append(f"- 奖杯: 🏆{detail.get('goldNum', 0)} 🥈{detail.get('silverNum', 0)} 🥉{detail.get('copperNum', 0)}")
    
    return "\n".join(res)

def present(data, file=sys.stdout):
    """呈现用户列表json数据"""
    if not data or 'roleID' not in data:
        return

    def format_time(timestamp):
        if timestamp == 0:
            return "无"
        return time.strftime('%Y-%m-%d', time.localtime(timestamp))

    print("=" * 35, f"用户列表总览 (共 {len(data['roleID'])} 人)", "=" * 35, sep='\n', file=file)

    for i in range(len(data['roleID'])):
        pid = data['roleID'][i]
        p_info = data['publicInfos'][i]
        s_status = data['spaceStatus'][i]
        status_desc = data['statusDesc'][i]
        is_top = "[置顶] " if data['isTop'][i] == 1 else ""
        
        name = p_info['name'].replace('\r', '').replace('\n', ' ')
        sex_str = '♀' if p_info['sex'] == '2' else '♂'
        vip_date = format_time(p_info['vipExpireTime'])
        
        mood_content = s_status['newMood'] if s_status['newMood'] else "无心情文本"
        media_info = ""
        if s_status.get('info'):
            media = s_status['info']
            media_info = f"\n    [媒体] 语音消息 ({media.get('timeSec')}秒): <a href=\"{media.get('uploadUrl')}\">链接</a>"
        
        lvl_info = p_info['levelInfo']
        exp_str = f"(Exp: {lvl_info['curExp']}/{lvl_info['nextExp']})"
        
        print(f"NO.{i+1} {is_top}{name} (ID: {pid})", file=file)
        print(f"    基础: {sex_str} | {p_info['age']}岁 | {p_info['area']} | IP: <a href=\"https://cip.cc/{p_info['ip']}\">{p_info['ip']}</a>", file=file)
        print(f"    账号: Lv.{lvl_info['level']} {exp_str} | VIP至: {vip_date} | Grade: {p_info['grade']}", file=file)
        print(f"    状态: {status_desc} | 游戏模式: {data['gameMode'][i]}", file=file)
        print(f"    动态: {mood_content}{media_info}", file=file)
        print("-" * 35, file=file)

def save_daily_record(target_data, daily_count, record_file):
    """保存每日统计记录到CSV"""
    if not target_data:
        return

    def to_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    best_overall = to_int(target_data.get('bestOverall', 0), 0)
    teamplay_best_times = to_int(target_data.get('teamplayBestTimes', 0), 0)
    free_battle_best_times = max(best_overall - teamplay_best_times, 0)
    kill_count = target_data.get('killCount', 0)
    grade = 0
    if 'publicInfos' in target_data:
        p_infos = target_data['publicInfos']
        if isinstance(p_infos, list) and len(p_infos) > 0:
            grade = p_infos[0].get('grade', 0)
        elif isinstance(p_infos, dict):
            grade = p_infos.get('grade', 0)
    elif 'publicInfo' in target_data:
        grade = target_data['publicInfo'].get('grade', 0)

    now = datetime.datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')

    # 保留原有字段并新增 FreeBattleBestTimes（自由战全场最佳数）
    header = ['Date', 'Time', 'BestOverall', 'FreeBattleBestTimes', 'KillCount', 'Grade', 'DailyFreeBattleCount']
    rows = []
    if os.path.exists(record_file):
        try:
            with open(record_file, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # 兼容旧文件：补齐新增列，历史数据保持原值不变
            for row in rows:
                row.setdefault('FreeBattleBestTimes', '')
        except Exception as e:
            print(f"读取旧记录失败: {e}")

    new_row = {
        'Date': date_str,
        'Time': time_str,
        'BestOverall': str(best_overall),
        'FreeBattleBestTimes': str(free_battle_best_times),
        'KillCount': str(kill_count),
        'Grade': str(grade),
        'DailyFreeBattleCount': str(daily_count)
    }

    found = False
    for i, row in enumerate(rows):
        if row.get('Date') == date_str:
            rows[i] = new_row
            found = True
            break
    
    if not found:
        rows.append(new_row)

    try:
        with open(record_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(rows)
        print(f"已{'更新' if found else '保存'}每日记录: {date_str} {time_str}")
    except Exception as e:
        print(f"写入记录失败: {e}")

def load_state(state_file):
    """读取上一次运行的状态"""
    if not os.path.exists(state_file):
        return {
            "last_status": 0,           # 0: 离线, >0: 在线
            "last_update_str": "",      # 上次更新时间字符串
            "daily_count": 0,           # 今日局数
            "record_date": ""           # 记录局数的那一天日期
        }
    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_state(state, state_file):
    """保存当前状态到文件"""
    try:
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"保存状态文件失败: {e}")

def main():
    config = load_config()
    if not config:
        print("配置文件加载失败，退出。")
        return
        
    accounts = config.get('accounts', [])
    
    if not accounts:
        print("配置文件中没有找到账号信息。")
        return

    print(f"开始监控，共 {len(accounts)} 个账号...")
    
    for account in accounts:
        roleID = account.get('roleID')
        targets = account.get('targets', [])
        note = account.get('note', roleID)
            
        print(f"\n>>> 正在使用账号: {note} (ID: {roleID})")
        
        if not account.get('authKey') or not roleID:
            print(f"账号 {note} 配置缺失 authKey 或 roleID，跳过。")
            continue
        
        if not targets:
            print(f"账号 {note} 未配置监控目标。")
            continue

        try:
            # 获取当前好友列表/状态 (make_request 会自动处理 -73 并重连)
            data = get_state_now(account)
            if not data:
                print(f"账号 {note} 获取数据为空，跳过。")
                continue

            for target in targets:
                target_id = target.get('id')
                target_name = target.get('name')
                
                if not target_id:
                    print(f"  目标配置缺失 ID，跳过。")
                    continue
                print(f"  > 正在检查目标: {target_name} (ID: {target_id})")

                target_idx = -1
                if 'roleID' in data and target_id in data['roleID']:
                    target_idx = data['roleID'].index(target_id)
                elif 'publicInfos' in data:
                    for i, info in enumerate(data['publicInfos']):
                        if info.get('name') == target_name:
                            target_idx = i
                            break
                
                # 初始化当前状态 (即使不在列表)
                current_status_code = 0
                current_mode = -1
                current_status_desc = "离线(未在列表)"
                
                if target_idx != -1:
                    current_status_code = data['status'][target_idx]
                    current_mode = data['gameMode'][target_idx]
                    current_status_desc = data['statusDesc'][target_idx]
                else:
                    print(f"    未在列表中找到目标: {target_name}。")

                state_file = os.path.join(os.path.dirname(__file__), f'monitor_state_{target_id}.json')
                record_file = os.path.join(os.path.dirname(__file__), f'monitor_daily_records_{target_id}.csv')

                try:
                    is_online_now = current_status_code > 0
                    state = load_state(state_file)
                    today_str = datetime.date.today().isoformat()
                    
                    if state.get('record_date') != today_str:
                        state['record_date'] = today_str
                        state['daily_count'] = 0
                        print(f"    [{target_name}] 日期变更，计数器已重置。")

                    if int(current_mode) == FREE_BATTLE_MODE_ID:
                        state['daily_count'] += 1
                        print(f"    [{target_name}] 检测到正在进行自由战，今日累计第 {state['daily_count']} 局。")
                    
                    was_online = state.get('last_status', 0) > 0
                    title = ""
                    msg = f"账号: {note}\n目标: {target_name}\n今日已玩自由战: {state['daily_count']} 局\n"
                    target_detail = {}
                    
                    if is_online_now and not was_online:
                        title = f"你关注的 [{target_name}] 上线了！状态: {current_status_desc}"
                    elif not is_online_now and was_online:
                        title = f"你关注的 [{target_name}] 下线了！最终状态: {current_status_desc}"
                        try:
                            target_detail = view_target(target_id, account)
                            save_daily_record(target_detail, state['daily_count'], record_file)
                        except Exception as e:
                            print(f"    保存记录时出错: {e}")

                    if title:
                        if is_online_now:
                            target_detail = view_target(target_id, account)
                        
                        # 格式化详细情况
                        msg += "\n" + format_target_detail(target_detail) + "\n"
                        buf = io.StringIO()
                        present(data, file=buf)
                        msg += "\n" + "-"*20 + "\n好友列表概况:\n" + buf.getvalue()
                        
                        send_notification(title, msg)
                    
                    state['last_status'] = current_status_code
                    state['last_update_str'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    save_state(state, state_file)
                    print(f"    [{target_name}]检查完毕。状态: {'在线' if is_online_now else '离线'}, 模式: {current_mode}\n{msg}")
                    
                except FatalAuthError:
                    raise FatalAuthError # 继续向上抛出，中断整个账号
                except Exception as e:
                    print(f"    处理目标 {target_name} 时发生错误: {e}")
                    import traceback
                    traceback.print_exc()

        except FatalAuthError:
            print(f"!!!! 账号 {note} 遭遇严重认证错误，已跳过剩余监控任务 !!!!")
            continue
        except Exception as e:
            print(f"账号 {note} 发生未预期的错误: {e}")
            continue

    print("\n所有账号监控任务执行完毕。")

if __name__ == '__main__':
    main()
