"""Regenerate paper plots with 100% precision, exact numbers matching paper_tmlr.tex,
and zero visual collisions.
"""
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = ROOT / 'outputs' / 'ablation-cnf-v3' / 'summary.json'
DOCS_DIR = ROOT / 'docs' / 'figures'
DOCS_DIR.mkdir(parents=True, exist_ok=True)

# Publication styling
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 9.5,
    'figure.titlesize': 14,
})

def plot_success_rates():
    # Load exact numbers
    budgets = [0.1, 1.0, 10.0]
    
    # Methods to display
    # We plot:
    # 1. Direct CNF (Glucose 4.2.1): 81.6%, 81.6%, 81.6%
    # 2. Learned Ranker (forest_full_selected): 20.8%, 74.4%, 80.4%
    # 3. Local Improvement Heuristic: 49.2%, 66.0%, 75.2%
    # 4. Sample Error Heuristic: 43.2%, 65.2%, 75.2%
    # 5. Ablated Forest (No-Need): 21.2%, 58.8%, 76.0%
    # 6. Legacy SMT (Z3): 4.0%, 56.8%, 80.0%
    
    cnf_rates = [81.6, 81.6, 81.6]
    learner_rates = [20.8, 74.4, 80.4]
    local_imp_rates = [49.2, 66.0, 75.2]
    sample_err_rates = [43.2, 65.2, 75.2]
    ablated_rates = [21.2, 58.8, 76.0]
    z3_rates = [4.0, 56.8, 80.0]
    
    fig, ax = plt.subplots(figsize=(8.2, 5.0), dpi=300)
    x = np.arange(len(budgets))
    
    # Plot background baselines first
    ax.plot(x, z3_rates, '-.x', label='Legacy SMT (Z3)', color='#666666', linewidth=1.8, markersize=6)
    ax.plot(x, ablated_rates, '--^', label='Ablated Forest (No-Need)', color='#7570b3', linewidth=1.8, markersize=6)
    ax.plot(x, sample_err_rates, ':d', label='Sample Error Heuristic', color='#e6ab02', linewidth=1.8, markersize=6)
    ax.plot(x, local_imp_rates, ':v', label='Local Improvement Heuristic', color='#e7298a', linewidth=1.8, markersize=6)
    
    # Plot primary methods prominently
    ax.plot(x, learner_rates, '-s', label='Learned Ranker (forest_full_selected)', color='#d95f02', linewidth=2.5, markersize=8)
    ax.plot(x, cnf_rates, '-o', label='Direct CNF (Glucose 4.2.1)', color='#1b9e77', linewidth=2.5, markersize=8)
    
    # Data callouts placed cleanly without overlap
    # At 0.1s:
    ax.annotate("81.6%", (0, 81.6), textcoords="offset points", xytext=(0, 7), ha='center',
                fontsize=9.5, fontweight='bold', color='#1b9e77')
    ax.annotate("20.8%", (0, 20.8), textcoords="offset points", xytext=(-16, -14), ha='center',
                fontsize=9.5, fontweight='bold', color='#d95f02')
    
    # At 1.0s:
    ax.annotate("81.6%", (1, 81.6), textcoords="offset points", xytext=(0, 7), ha='center',
                fontsize=9.5, fontweight='bold', color='#1b9e77')
    ax.annotate("74.4%", (1, 74.4), textcoords="offset points", xytext=(0, 9), ha='center',
                fontsize=9.5, fontweight='bold', color='#d95f02')
    
    # At 10.0s:
    # CNF is 81.6%, Learner is 80.4% -> place CNF above, Learner slightly to the left/bottom to avoid collision
    ax.annotate("81.6%", (2, 81.6), textcoords="offset points", xytext=(12, 6), ha='left',
                fontsize=9.5, fontweight='bold', color='#1b9e77')
    ax.annotate("80.4%", (2, 80.4), textcoords="offset points", xytext=(12, -10), ha='left',
                fontsize=9.5, fontweight='bold', color='#d95f02')
    
    ax.set_ylabel('Repair Success Rate on Larger Circuits (%)', labelpad=8)
    ax.set_xlabel('Execution Time Budget (Wall-Clock)', labelpad=8)
    ax.set_title('Repair Success Rate Across Wall-Clock Deadlines (N = 250)', pad=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(['0.1 s', '1.0 s', '10.0 s'])
    ax.set_ylim(-3, 96)
    ax.set_xlim(-0.25, 2.35)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(frameon=True, facecolor='white', framealpha=0.92, loc='lower right', edgecolor='#cccccc')
    
    plt.tight_layout()
    out_png = DOCS_DIR / 'success_vs_budget.png'
    out_pdf = DOCS_DIR / 'success_vs_budget.pdf'
    plt.savefig(out_png, dpi=300)
    plt.savefig(out_pdf)
    plt.close()
    print(f"Generated clean success_vs_budget: {out_png}")


def plot_latency_breakdown():
    # Exact numbers from paper_tmlr.tex (Section 6.1 for forest_full_selected, N=186 mutual cases):
    # Candidate & Feature Extraction: 49.7 ms
    # Decision Forest Inference: 92.7 ms
    # Candidate Sorting: 2.4 ms
    # Total Upfront Overhead: 144.8 ms
    # Subsequent Verification Loop: 55.1 ms
    # Total Learned Elapsed: 199.9 ms (or 202.0 ms recorded)
    # Complete Direct CNF: 16.7 ms
    
    feat_ms = 49.7
    infer_ms = 92.7
    sort_ms = 2.4
    overhead_ms = feat_ms + infer_ms + sort_ms  # 144.8 ms
    verif_ms = 55.1
    total_learned_ms = overhead_ms + verif_ms   # 199.9 ms
    cnf_ms = 16.7
    
    # We increase the figure height and adjust ylim and title pad so the arrow and text have plenty of headroom!
    fig, ax = plt.subplots(figsize=(8.5, 3.8), dpi=300)
    methods = ['Direct CNF\n(Glucose 4.2.1)', 'Learned Ranker\n(forest_full_selected)']
    y = np.array([0.3, 1.1])
    height = 0.38
    
    # Direct CNF bar
    ax.barh(y[0], cnf_ms, height, label=f'CNF Solving & CEGIS Checking ({cnf_ms:.1f} ms)', color='#1b9e77')
    ax.text(cnf_ms + 4, y[0], f'{cnf_ms:.1f} ms total', va='center', fontsize=9.5, fontweight='bold', color='#1b9e77')
    
    # Learned Ranker stacked bar
    left = 0
    ax.barh(y[1], feat_ms, height, label=f'Feature Extraction ({feat_ms:.1f} ms)', color='#fdae61', left=left)
    left += feat_ms
    ax.barh(y[1], infer_ms, height, label=f'Forest Inference ({infer_ms:.1f} ms)', color='#d7191c', left=left)
    left += infer_ms
    ax.barh(y[1], sort_ms, height, label=f'Sorting ({sort_ms:.1f} ms)', color='#fee08b', left=left)
    left += sort_ms
    ax.barh(y[1], verif_ms, height, label=f'Verification Loop ({verif_ms:.1f} ms)', color='#2c7bb6', left=left)
    
    ax.text(left + 5, y[1], f'{total_learned_ms:.1f} ms total', va='center', fontsize=9.5, fontweight='bold', color='#2c7bb6')
    
    # Overhead bracket/arrow annotation ABOVE the bar with ample vertical clearance
    arrow_y = y[1] + height / 2 + 0.08
    text_y = arrow_y + 0.07
    
    ax.annotate('', xy=(overhead_ms, arrow_y), xytext=(0, arrow_y),
                arrowprops=dict(arrowstyle='<->', color='#b2182b', lw=1.6))
    ax.text(overhead_ms / 2, text_y, f'Upfront Guidance Overhead: {overhead_ms:.1f} ms',
            ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#b2182b')
    
    ax.set_yticks(y)
    ax.set_yticklabels(methods, fontsize=10.5)
    ax.set_xlabel('Mean Wall-Clock Latency (Milliseconds)', labelpad=8)
    ax.set_title("Fine-Grained Latency Breakdown on Matched Solved Instances (N = 186)", pad=22, fontweight='bold')
    ax.set_xlim(0, 260)
    ax.set_ylim(-0.1, 1.65)  # Plenty of headroom above the arrow!
    ax.grid(axis='x', linestyle='--', alpha=0.5)
    ax.legend(loc='center right', fontsize=8.5, framealpha=0.92, edgecolor='#cccccc')
    
    plt.tight_layout()
    out_png = DOCS_DIR / 'latency_breakdown.png'
    out_pdf = DOCS_DIR / 'latency_breakdown.pdf'
    plt.savefig(out_png, dpi=300)
    plt.savefig(out_pdf)
    plt.close()
    print(f"Generated clean latency_breakdown: {out_png}")

if __name__ == '__main__':
    plot_success_rates()
    plot_latency_breakdown()
