import os
root = r'E:\codex Project\work1\Alignment_Engine'
exts = {'py': 0, 'js': 0, 'ts': 0, 'tsx': 0, 'css': 0, 'md': 0, 'cpp': 0, 'h': 0}
totals = 0
files = 0
for dp, dn, fns in os.walk(root):
    if 'node_modules' in dp or '.git' in dp or '__pycache__' in dp:
        continue
    for fn in fns:
        ext = os.path.splitext(fn)[1].lstrip('.')
        if ext in exts:
            path = os.path.join(dp, fn)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = sum(1 for _ in f)
                    totals += lines
                    files += 1
                    exts[ext] += lines
            except:
                pass
print(f'Total lines: {totals}')
print(f'Files scanned: {files}')
for e, v in sorted(exts.items()):
    print(f'  .{e}: {v} lines')
