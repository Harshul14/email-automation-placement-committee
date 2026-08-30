import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('Working_Prototype_P2.ipynb', encoding='utf-8') as f:
    nb = json.load(f)

for i, c in enumerate(nb['cells']):
    ctype = c['cell_type']
    print(f'=== Cell {i} ({ctype}) ===')
    print(''.join(c['source']))
    print()
