with open('docs/paper_tmlr.tex', 'r', encoding='utf-8') as f:
    text = f.read()

# Check lines around 40-50
lines = text.splitlines()
for i in range(40, 55):
    print(f"{i+1}: {lines[i]}")

print("---")
# Check lines around 85-100
for i in range(85, 100):
    print(f"{i+1}: {lines[i]}")

