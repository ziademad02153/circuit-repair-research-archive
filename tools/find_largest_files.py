import os

sizes = []
for root, dirs, files in os.walk('.'):
    if '.git' in root:
        continue
    for f in files:
        p = os.path.join(root, f)
        sizes.append((p, os.path.getsize(p)))

sizes.sort(key=lambda x: x[1], reverse=True)
print("Top 15 largest files:")
for p, s in sizes[:15]:
    print(f"  {p}: {s / (1024*1024):.2f} MB")

