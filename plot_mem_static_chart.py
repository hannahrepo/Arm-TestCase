import matplotlib.pyplot as plt
import os

def parse_bw(filename):
    """解析 bw_mem 输出: '128.00 12345.67' """
    vals = []
    if not os.path.exists(filename): return [0,0,0]
    with open(filename, 'r') as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    vals.append(float(parts[1]))
                except ValueError: continue
    while len(vals) < 3: vals.append(0)
    return vals

def parse_lat(filename):
    """
    解析函数：
    使用 split() 兼容整数、浮点数和科学计数法
    """
    sizes, lats = [], []
    if not os.path.exists(filename): return sizes, lats
    with open(filename, 'r') as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    s = float(parts[0])
                    l = float(parts[1])
                    if s > 0:
                        sizes.append(s)
                        lats.append(l)
                except ValueError: continue
    # 排序，防止绘图折线乱跳
    data = sorted(zip(sizes, lats))
    if not data: return [], []
    return zip(*data)

# --- 绘图逻辑 ---

bw_labels = ['Read', 'Write', 'Copy']
big_vals = parse_bw("bw_big.txt")
little_vals = parse_bw("bw_little.txt")

# 创建画布
fig = plt.figure(figsize=(16, 7))

# 1. 带宽对比图
ax1 = fig.add_subplot(1, 2, 1)
x = range(len(bw_labels))
ax1.bar([i-0.2 for i in x], big_vals, width=0.4, label='Big Core (A76)', color='teal', zorder=3)
ax1.bar([i+0.2 for i in x], little_vals, width=0.4, label='Little Core (A55)', color='salmon', zorder=3)
ax1.set_xticks(x)
ax1.set_xticklabels(bw_labels)
ax1.set_ylabel('Bandwidth (MB/s)')
ax1.set_title('RK3588 Memory Bandwidth (Big vs Little)', fontsize=14, pad=15)
ax1.legend()
ax1.grid(axis='y', linestyle='--', alpha=0.7, zorder=0)

# 2. 延迟曲线对比图
ax2 = fig.add_subplot(1, 2, 2)

s_lin, l_lin = parse_lat("latency_linear.txt")
s_ran, l_ran = parse_lat("latency_random.txt")

if s_lin:
    ax2.plot(s_lin, l_lin, 'o-', markersize=4, linewidth=2, color='darkblue', label='Linear (Prefetcher ON)')

if s_ran:
    ax2.plot(s_ran, l_ran, 's-', markersize=4, linewidth=2, color='crimson', label='Random (True Latency)')

# 设置双对数坐标 (更科学地展示 Cache 到 DRAM 的飞跃)
ax2.set_xscale('log')
# 如果希望 Y 轴更直观，可以用 linear，如果想看清 L1/L2 细节，建议用 log
# ax2.set_yscale('log') 

ax2.set_xlabel('Working Set Size (MB)', fontsize=12)
ax2.set_ylabel('Latency (ns)', fontsize=12)
ax2.set_title('RK3588 Latency: The "Memory Wall" Truth', fontsize=14, pad=15)

# 自动获取最大延迟以确定标注位置
max_y = max(max(l_lin) if l_lin else 1, max(l_ran) if l_ran else 1)
ax2.set_ylim(0, max_y * 1.1) 

# 标注 Cache 边界辅助线
boundaries = [0.064, 0.512, 4.0]
colors = ['red', 'green', 'orange']
labels = ['L1', 'L2', 'L3/SLC']

for b, c, l in zip(boundaries, colors, labels):
    ax2.axvline(x=b, color=c, linestyle=':', alpha=0.6)
    # 在顶部标注文字
    ax2.text(b, max_y * 1.02, l, color=c, fontsize=10, weight='bold', ha='center')

ax2.text(10, max_y * 1.02, "DRAM", color='gray', fontsize=10, weight='bold', ha='center')

ax2.grid(True, which="both", linestyle='--', alpha=0.5)
ax2.legend(loc='upper left')

plt.tight_layout()
plt.savefig('rk3588_memory_comprehensive_report.png', dpi=300)
print("Plotting success! File: rk3588_memory_comprehensive_report.png")
plt.show()
