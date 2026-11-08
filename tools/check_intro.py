with open('docs/paper_tmlr.tex', 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.splitlines()
for i in range(24, 41):
    print(f"{i+1}: {lines[i]}")

