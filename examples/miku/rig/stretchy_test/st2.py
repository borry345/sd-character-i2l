"""Stretchy Studio: load a PSD, walk the import wizard step by step, screenshot each step.
usage: st2.py <psd> <tag> [actions...]   actions: click:<text> | wait:<ms> | shot:<name>"""
import os, sys
from playwright.sync_api import sync_playwright
T = os.path.dirname(os.path.abspath(__file__))
psd, tag, acts = sys.argv[1], sys.argv[2], sys.argv[3:]
with sync_playwright() as p:
    b = p.chromium.launch(channel='msedge', headless=True, args=['--enable-unsafe-swiftshader', '--use-angle=swiftshader'])
    pg = b.new_page(viewport={'width': 1600, 'height': 1000})
    logs = []
    pg.on('console', lambda m: logs.append(f'{m.type}: {m.text}'[:220]))
    pg.on('pageerror', lambda e: logs.append(f'PAGEERROR: {e}'[:300]))
    pg.goto('https://editor.stretchy.studio', wait_until='networkidle', timeout=90000)
    pg.wait_for_timeout(2000)
    pg.locator('input[type=file]').set_input_files(psd)
    pg.wait_for_timeout(5000)
    pg.screenshot(path=f'{T}/st_{tag}_01_loaded.png')
    for a in acts:
        k, _, v = a.partition(':')
        if k == 'click':
            pg.get_by_text(v, exact=False).first.click(timeout=20000)
            pg.wait_for_timeout(2500)
        elif k == 'btn':
            pg.get_by_role('button', name=v, exact=True).first.click(timeout=20000)
            pg.wait_for_timeout(2500)
        elif k == 'waittext':  # wait until text appears (max 240 s)
            pg.get_by_text(v, exact=False).first.wait_for(timeout=240000)
        elif k == 'wait':
            pg.wait_for_timeout(int(v))
        elif k == 'shot':
            pg.screenshot(path=f'{T}/st_{tag}_{v}.png')
    body = pg.locator('body').inner_text()
    print(body[:2500])
    print('---- buttons', [t.strip()[:40] for t in pg.locator('button').all_inner_texts() if t.strip()][:60])
    print('---- logs'); print('\n'.join(logs[-15:]))
    b.close()
