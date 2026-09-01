import json

nb = json.load(open('week2/02-lstm/real_stock_lstm_compare.ipynb'))

# Fix cell 8 (index 7) - use separate line bounds for each plot
cell8_code = """fig, axes = plt.subplots(1, 2, figsize=(14, 5))

axes[0].scatter(y_test, mlp_test_pred, alpha=0.5, s=10, label='MLP test', color='tab:blue')
line_mlp = np.linspace(np.min(y_test), np.max(y_test), 200)
axes[0].plot(line_mlp, line_mlp, color='black', linestyle='--', lw=1, label='perfect forecast')
axes[0].set_title('Predicted vs actual returns (MLP)')
axes[0].set_xlabel('actual return')
axes[0].set_ylabel('predicted return')
axes[0].legend()
axes[0].grid(alpha=0.3)

axes[1].scatter(y_test_seq[:500], lstm_test_pred[:500], s=10, alpha=0.5, label='LSTM test', color='tab:orange')
line_lstm = np.linspace(np.min(y_test_seq), np.max(y_test_seq), 200)
axes[1].plot(line_lstm, line_lstm, color='black', linestyle='--', lw=1, label='perfect forecast')
axes[1].set_title('Predicted vs actual returns (LSTM)')
axes[1].set_xlabel('actual return')
axes[1].set_ylabel('predicted return')
axes[1].legend()
axes[1].grid(alpha=0.3)

plt.tight_layout()
plt.show()
"""

# Convert to source format (list of strings, each with newline)
cell8_source = [line + '\n' for line in cell8_code.split('\n')]

nb['cells'][7]['source'] = cell8_source

json.dump(nb, open('week2/02-lstm/real_stock_lstm_compare.ipynb', 'w'), indent=1)
print('✓ Fixed cell 8: using separate line bounds for each plot (line_mlp and line_lstm)')
