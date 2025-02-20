import os
import subprocess
from datetime import datetime

def get_system_stats():
    """システムの状態を取得する関数（サーバー環境用）"""
    try:
        stats = {
            'cpu': get_cpu_usage(),
            'memory': get_memory_usage(),
            'disk': get_disk_usage(),
            'process': get_process_info()
        }
        return stats
    except Exception as e:
        return {'error': str(e)}

def get_cpu_usage():
    """CPU使用率を取得（top/mpstatコマンド使用）"""
    try:
        # mpstatがある場合
        cmd = "mpstat 1 1 | awk 'END{print 100-$NF}'"
        cpu_percent = float(subprocess.check_output(cmd, shell=True).decode().strip())
        return {
            'percent': cpu_percent,
            'cores': os.cpu_count() or 1
        }
    except:
        try:
            # topコマンドを使用する場合
            cmd = "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'"
            cpu_percent = float(subprocess.check_output(cmd, shell=True).decode().strip())
            return {
                'percent': cpu_percent,
                'cores': os.cpu_count() or 1
            }
        except:
            return {'percent': 0, 'cores': 1}

def get_memory_usage():
    """メモリ使用状況を取得（free コマンド使用）"""
    try:
        cmd = "free -m | awk 'NR==2{printf \"%.2f\", $3*100/$2 }'"
        memory_percent = float(subprocess.check_output(cmd, shell=True).decode().strip())
        
        # 合計メモリ量を取得
        cmd_total = "free -g | awk 'NR==2{print $2}'"
        total_memory = float(subprocess.check_output(cmd_total, shell=True).decode().strip())
        
        return {
            'percent': memory_percent,
            'total': total_memory,
            'available': total_memory * (100 - memory_percent) / 100
        }
    except:
        return {'percent': 0, 'total': 0, 'available': 0}

def get_disk_usage():
    """ディスク使用状況を取得（df コマンド使用）"""
    try:
        cmd = "df -h / | awk 'NR==2{print $5}' | sed 's/%//'"
        disk_percent = float(subprocess.check_output(cmd, shell=True).decode().strip())
        
        # 合計容量を取得
        cmd_total = "df -h / | awk 'NR==2{print $2}'"
        total = subprocess.check_output(cmd_total, shell=True).decode().strip()
        
        # 使用可能容量を取得
        cmd_available = "df -h / | awk 'NR==2{print $4}'"
        available = subprocess.check_output(cmd_available, shell=True).decode().strip()
        
        return {
            'percent': disk_percent,
            'total': total,
            'available': available
        }
    except:
        return {'percent': 0, 'total': '0G', 'available': '0G'}

def get_process_info():
    """実行中のプロセス情報を取得（ps コマンド使用）"""
    try:
        cmd = "ps aux --sort=-%cpu | head -n 6 | tail -n 5"
        output = subprocess.check_output(cmd, shell=True).decode()
        
        processes = []
        for line in output.split('\n'):
            if line.strip():
                parts = line.split()
                processes.append({
                    'user': parts[0],
                    'pid': parts[1],
                    'cpu': float(parts[2]),
                    'mem': float(parts[3]),
                    'command': ' '.join(parts[10:])[:30]
                })
        return processes
    except:
        return []

def get_server_load():
    """サーバーの負荷状況を取得（uptime コマンド使用）"""
    try:
        cmd = "uptime | awk -F'[a-z]:' '{ print $2}'"
        load = subprocess.check_output(cmd, shell=True).decode().strip()
        return {
            'load': load,
            'uptime': get_uptime()
        }
    except:
        return {'load': 'N/A', 'uptime': 'N/A'}

def get_uptime():
    """サーバーの稼働時間を取得"""
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
            
        days = int(uptime_seconds / 86400)
        hours = int((uptime_seconds % 86400) / 3600)
        minutes = int((uptime_seconds % 3600) / 60)
        
        return f"{days}日 {hours}時間 {minutes}分"
    except:
        return 'N/A'