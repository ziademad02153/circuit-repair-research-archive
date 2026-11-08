with open('README.md', 'r', encoding='utf-8') as f:
    text = f.read()

for i, line in enumerate(text.splitlines()):
    if any(k in line.lower() for k in ['ziad', 'zelsay', 'elsayed', 'github.com']):
        print(f"README.md line {i+1}: {line}")

print("---")
with open('CITATION.cff', 'r', encoding='utf-8') as f:
    text = f.read()

for i, line in enumerate(text.splitlines()):
    if any(k in line.lower() for k in ['ziad', 'zelsay', 'elsayed', 'github.com']):
        print(f"CITATION.cff line {i+1}: {line}")

