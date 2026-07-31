#!/usr/bin/env python3
"""check-contrast.py — 设计系统对比度门槛检查 (WCAG AA 4.5:1)
用法: python3 check-contrast.py [design-tokens.css]
规则: 解析 :root 中的 --clr-* 色 token, 校验每个深色语义/文字 token 在
      白底 (#ffffff) 和对应浅背景 (--clr-*-bg) 上的对比度。
      失败 → 退出码 1, 阻止推送。全部通过 → 退出码 0。
"""
import re
import sys

AA = 4.5

def parse_tokens(path):
    text = open(path, encoding='utf-8').read()
    root = re.search(r':root\s*{(.*?)}', text, re.S)
    if not root:
        sys.exit('ERROR: 未找到 :root 块')
    tokens = {}
    for m in re.finditer(r'(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]+\))\s*;', root.group(1)):
        tokens[m.group(1)] = m.group(2)
    return tokens

def lum(hexs):
    hexs = hexs.lstrip('#')
    if len(hexs) in (3, 4):
        hexs = ''.join(c * 2 for c in hexs[:3])
    r, g, b = (int(hexs[i:i+2], 16) / 255 for i in (0, 2, 4))
    def f(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = f(r), f(g), f(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'design-tokens.css'
    t = parse_tokens(path)
    checks = []
    # 文字色 on 白底
    for name in ('--clr-text', '--clr-text-secondary', '--clr-text-muted'):
        if name in t:
            checks.append((name, t[name], '#ffffff'))
    # 语义色 on 白底 + on 对应浅背景
    for sem in ('success', 'warning', 'error', 'info'):
        fg = t.get(f'--clr-{sem}')
        bg = t.get(f'--clr-{sem}-bg')
        if fg:
            checks.append((f'--clr-{sem}', fg, '#ffffff'))
            if bg:
                checks.append((f'--clr-{sem} on {sem}-bg', fg, bg))
    # 按钮: 白字 on 主色/强调色
    for btn in ('--clr-primary-700', '--clr-primary-800', '--clr-accent-700'):
        if btn in t:
            checks.append((f'white on {btn}', '#ffffff', t[btn]))

    fails = 0
    print(f'{"check":<38} {"ratio":>6}  {"AA 4.5":>7}')
    for name, a, b in checks:
        r = contrast(a, b)
        ok = r >= AA
        fails += 0 if ok else 1
        print(f'{name:<38} {r:>6.2f}  {"PASS" if ok else "FAIL"}')
    print(f'\n{"✅ 全部通过" if fails == 0 else f"❌ {fails} 项失败 — 禁止推送"}')
    sys.exit(0 if fails == 0 else 1)

if __name__ == '__main__':
    main()
