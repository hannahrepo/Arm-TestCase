#!/usr/bin/env python3
import os
import subprocess
import time
import sys

# --- 配置区 ---
MEM_SIZE = "128M"           # 带宽测试数据量
LAT_LINEAR_SIZE = "64M"      # 线性延迟测试上限 (Stride 128)
LAT_RANDOM_SIZE = "16M"      # 真实延迟测试上限 (Stride 160)
BW_BIG_FILE = "bw_big.txt"
BW_LITTLE_FILE = "bw_little.txt"
LATENCY_LINEAR_FILE = "latency_linear.txt"
LATENCY_RANDOM_FILE = "latency_random.txt"

# 自动搜索 DMC (内存控制器) 路径
DMC_PATHS = [
    "/sys/class/devfreq/fb000000.dmc",
    "/sys/class/devfreq/dmc",
    "/sys/devices/platform/fb000000.dmc/devfreq/fb000000.dmc"
]

def run_command(cmd, timeout=300):
    """运行系统命令并捕获输出，增加超时机制"""
    try:
        result = subprocess.run(
            cmd, shell=True, check=True, 
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
            universal_newlines=True, timeout=timeout
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "ERROR: Command Timeout"
    except subprocess.CalledProcessError as e:
        return f"ERROR: {e.stderr}"

def get_detailed_core_logic():
    """扫描全核，通过频率特征准确识别 4+4 架构"""
    freqs = {}
    for i in range(8):
        path = f"/sys/devices/system/cpu/cpu{i}/cpufreq/cpuinfo_max_freq"
        if os.path.exists(path):
            with open(path, 'r') as f:
                try:
                    f_val = int(f.read().strip())
                    if f_val not in freqs: freqs[f_val] = []
                    freqs[f_val].append(i)
                except:
                    continue
    
    if not freqs:
        return None

    # 排序所有检测到的频率频率
    sorted_freq_keys = sorted(freqs.keys())
    
    # 最低主频的是小核 (Cluster 0: CPU 0-3)
    little_f = sorted_freq_keys[0]
    little_cores = freqs[little_f]
    
    # 其余所有频率的核心都归类为大核 (Cluster 1&2: CPU 4-7)
    big_cores = []
    big_freqs_found = []
    for f in sorted_freq_keys[1:]:
        big_cores.extend(freqs[f])
        big_freqs_found.append(f // 1000)
    
    big_cores.sort() 

    return {
        "little_cores": little_cores,
        "little_freq": little_f // 1000,
        "big_cores": big_cores,
        "big_freq": big_freqs_found[-1] 
    }

def set_hardware_perf(mode="performance"):
    """设置频率锁定模式"""
    print(f"[+] 正在切换硬件模式至: {mode}")
    
    # 锁定 CPU 频率
    for i in range(8):
        gov_file = f"/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_governor"
        if os.path.exists(gov_file):
            subprocess.run(f"echo {mode} > {gov_file}", shell=True)

    # 锁定内存控制器(DMC)频率
    for path in DMC_PATHS:
        gov_file = f"{path}/governor"
        if os.path.exists(gov_file):
            target = "performance" if mode == "performance" else "simple_ondemand"
            subprocess.run(f"echo {target} > {gov_file}", shell=True)
            print(f"    - 已配置 DMC: {path}")

def main():
    if os.geteuid() != 0:
        print("错误: 必须以 root 权限运行此脚本！")
        sys.exit(1)

    info = get_detailed_core_logic()
    if not info:
        print("错误: 无法识别 CPU 架构。")
        sys.exit(1)

    print(f"[*] 检测到 RK3588 架构:")
    print(f"    - 小核簇: CPU {info['little_cores']} | 主频: {info['little_freq']}MHz")
    print(f"    - 大核簇: CPU {info['big_cores']} | 主频: {info['big_freq']}MHz")

    try:
        set_hardware_perf("performance")
        time.sleep(2)

        # 1. 带宽测试
        for c_type in ["big", "little"]:
            c_id = info[f"{c_type}_cores"][0]
            print(f"[1/3] 正在测试 {c_type.upper()} 核带宽 (使用 CPU {c_id})...")
            res_list = []
            for op in ["rd", "wr", "cp"]:
                out = run_command(f"taskset -c {c_id} bw_mem {MEM_SIZE} {op}")
                res_list.append(out.strip())
            
            with open(BW_BIG_FILE if c_type == "big" else BW_LITTLE_FILE, "w") as f:
                f.write("\n".join(res_list))

        # 2. 线性延迟测试
        print(f"[2/3] 正在执行线性延迟测试 (Stride=128, Upper {LAT_LINEAR_SIZE})...")
        res_lin = run_command(f"taskset -c {info['big_cores'][0]} lat_mem_rd -N 1 -W 0 {LAT_LINEAR_SIZE} 128")
        with open(LATENCY_LINEAR_FILE, "w") as f:
            f.write(res_lin)

        # 3. 真实延迟测试 (Stride 160)
        print(f"[3/3] 正在执行真实延迟测试 (Stride=160, Upper {LAT_RANDOM_SIZE})...")
        print("      提示: 使用 Stride 160 绕过预取，探测真实 LPDDR 物理延迟...")
        
        res_ran = run_command(f"taskset -c {info['big_cores'][0]} lat_mem_rd -N 1 -W 0 {LAT_RANDOM_SIZE} 160", timeout=300)
        with open(LATENCY_RANDOM_FILE, "w") as f:
            f.write(res_ran)

        print(f"\n[OK] 测试完成！")
        print(f"    - 带宽结果: {BW_BIG_FILE}, {BW_LITTLE_FILE}")
        print(f"    - 延迟结果: {LATENCY_LINEAR_FILE}, {LATENCY_RANDOM_FILE}")

    finally:
        set_hardware_perf("schedutil")
        print("[+] 已恢复节能模式。")

if __name__ == "__main__":
    main()
