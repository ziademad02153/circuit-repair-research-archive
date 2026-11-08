import re

with open('docs/paper_tmlr.tex', 'r', encoding='utf-8') as f:
    text = f.read()

phrases = [
    'Rather than discarding or reformulating',
    'pre-registered validation endpoints',
    'ensuring equal effective gradient contribution',
    'intractable',
    'ranking imprecision under cross-size distribution shift',
    'jha2010oracle',
    'xu2008satzilla'
]

print("Phrase search results:")
for p in phrases:
    matches = [i+1 for i, line in enumerate(text.splitlines()) if p in line]
    print(f'"{p}": count={len(matches)}, lines={matches}')

