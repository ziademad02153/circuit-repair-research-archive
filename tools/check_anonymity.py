import os

# Check for identity leaks (usernames, paths, author names)
identity_tokens = ['zelsay', 'elsayed', 'ziad']
matches = []

for root, dirs, files in os.walk('.'):
    if '.git' in root or '__pycache__' in root or 'docs\\figures' in root:
        continue
    for file in files:
        if file.endswith(('.py', '.tex', '.md', '.txt', '.json', '.bib', '.cff', '.yaml', '.yml')):
            p = os.path.join(root, file)
            try:
                content = open(p, encoding='utf-8', errors='ignore').read()
                for token in identity_tokens:
                    if token in content.lower():
                        matches.append((p, token))
            except:
                pass

print(f"Total potential identity leaks found: {len(matches)}")
for p, token in matches:
    print(f"  {p}: matches '{token}'")

