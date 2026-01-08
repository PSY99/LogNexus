import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

# ==========================================
# 1. Data Preparation
# ==========================================

# lognexus One-time Cost (Initialization)
lognexus_input_total = 84431
lognexus_output_total = 49201
lognexus_total_cost = lognexus_input_total + lognexus_output_total

# Direct LLM Cost (Per 100 logs) - Raw Data from your image
# I have transcribed the numbers from your image accurately.
direct_inputs = [
 4319, 8868, 8586, 9019, 9628, 9617, 8461, 9587, 8633, 8307,
 9187, 8677, 9332, 7231, 9244, 9430, 7571, 9708, 8061, 6787,
 7766, 7801, 9788, 8974, 9297, 5890, 5933, 6417, 7568, 9200
]

direct_outputs = [
 2729, 4230, 6653, 3551, 4860, 3532, 6912, 3614, 4917, 5360,
 5038, 4449, 4807, 6071, 3773, 4890, 5689, 3642, 5023, 4898,
 4769, 4242, 5606, 4945, 3818, 6979, 9632, 9347, 4740, 5693
]

# Calculate cumulative cost for Direct LLM
batch_size = 100
x_real = np.arange(1, len(direct_inputs) + 1) * batch_size
y_direct_real = np.cumsum(np.array(direct_inputs) + np.array(direct_outputs))

# Calculate Average Cost per Log for Projection
avg_tokens_per_100 = np.mean(np.array(direct_inputs) + np.array(direct_outputs))
avg_tokens_per_log = avg_tokens_per_100 / batch_size

# ==========================================
# 2. Projection & Break-even Calculation
# ==========================================

# Define projection range (e.g., up to 5000 logs to show the gap clearly)
x_project = np.linspace(0, 5000, 100)

# lognexus Cost Function: y = C (Constant after init)
# Note: In reality, lognexus has 0 cost at x=0, but incurs the full cost 
# immediately during the "Phase 1" setup. We model this as a flat line 
# starting from the y-intercept.
y_lognexus_project = np.full_like(x_project, lognexus_total_cost)

# Direct LLM Cost Function: y = kx
y_direct_project = x_project * avg_tokens_per_log

# Find Break-even point (Intersection)
break_even_x = lognexus_total_cost / avg_tokens_per_log

# ==========================================
# 3. Plotting (Academic Style)
# ==========================================

plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman']
plt.rcParams['font.size'] = 12

fig, ax = plt.subplots(figsize=(8, 5))

# Plot Direct LLM (Real Data Points)
ax.scatter(x_real, y_direct_real, color='#d62728', s=20, alpha=0.6, label='Direct LLM (Observed)')

# Plot Direct LLM (Projection)
ax.plot(x_project, y_direct_project, color='#d62728', linestyle='--', linewidth=2, label='Direct LLM (Trend)')

# Plot lognexus (Constant Cost)
ax.plot(x_project, y_lognexus_project, color='#1f77b4', linewidth=2.5, label='lognexus (Total Cost)')

# Highlight Break-even Point
ax.plot(break_even_x, lognexus_total_cost, 'ko', markersize=8, zorder=10)
ax.annotate(f'Break-even Point\n~{int(break_even_x)} Logs', 
 xy=(break_even_x, lognexus_total_cost), 
 xytext=(break_even_x + 200, lognexus_total_cost - 90000),
 arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=.2'),
 fontsize=11, fontweight='bold')

# Fill the area to show savings
ax.fill_between(x_project, y_lognexus_project, y_direct_project, 
 where=(x_project > break_even_x), 
 color='green', alpha=0.1, hatch='//', label='Token Savings')

# Formatting
def k_formatter(x, pos):
 return f'{int(x/1000)}k'

ax.xaxis.set_major_formatter(FuncFormatter(k_formatter))
ax.yaxis.set_major_formatter(FuncFormatter(k_formatter))

ax.set_xlabel('Number of Processed Logs', fontsize=14)
ax.set_ylabel('Cumulative Token Consumption', fontsize=14)
ax.set_title('Cost Analysis: lognexus vs. Direct LLM', fontsize=16, pad=15)
ax.legend(loc='upper left', frameon=True, fontsize=11)
ax.grid(True, linestyle=':', alpha=0.6)

# Layout adjustment
plt.tight_layout()

# Save
plt.savefig('fig_cost_analysis.png', dpi=300, bbox_inches='tight')
plt.show()

print(f"lognexus Total Cost: {lognexus_total_cost}")
print(f"Direct LLM Avg Cost per Log: {avg_tokens_per_log:.2f}")
print(f"Break-even Point: {break_even_x:.2f} logs")
