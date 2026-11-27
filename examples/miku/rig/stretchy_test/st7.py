"""Elbow-only bend (90 deg) on the image-left arm (Stretchy 'rightElbow'), and knee-only bend, two ways:
  old : PSD -> wizard -> set pivots afterwards (weights stay from the guessed pivots)
  file: open the .stretch (pivots set before remesh)"""
import os, re, sys
from playwright.sync_api import sync_playwright
T = os.path.dirname(os.path.abspath(__file__))
mode, src, tag = sys.argv[1], sys.argv[2], sys.argv[3]
PIV = {'rightArm': (488.3, 480), 'rightElbow': (466.1, 554.8), 'rightLeg': (497.4, 620), 'rightKnee': (484.8, 721.9)}
ROT = [('rightElbow', 90), ('rightKnee', -60)]


def expand(pg):
    for _ in range(30):
        c = pg.locator('button:has(svg[style*="rotate(0deg)"] path[d="M3 2l4 3-4 3"])')
        if c.count() == 0:
            break
        c.first.click(); pg.wait_for_timeout(200)


with sync_playwright() as p:
    b = p.chromium.launch(channel='msedge', headless=True)
    pg = b.new_page(viewport={'width': 1600, 'height': 1000})
    pg.goto('https://editor.stretchy.studio', wait_until='networkidle', timeout=90000)
    pg.wait_for_timeout(2000)
    pg.locator('input[type=file]').set_input_files(src)
    pg.wait_for_timeout(6000)
    num = pg.locator('input[type=number]')
    if mode == 'old':
        pg.get_by_role('button', name='Continue →').click(); pg.wait_for_timeout(3000)
        pg.get_by_text('Next: Adjust Joints').click(); pg.wait_for_timeout(3000)
        pg.get_by_role('button', name='Finish Setup').click(); pg.wait_for_timeout(8000)
        for g, (x, y) in PIV.items():
            pg.get_by_text(g, exact=True).first.click(); pg.wait_for_timeout(500)
            for idx, val in ((5, x), (6, y)):
                e = num.nth(idx); e.fill(str(val)); e.press('Enter'); pg.wait_for_timeout(200)
    elif mode == 'remesh':  # same as old, then Remesh every limb layer (no save/load)
        pg.get_by_role('button', name='Continue →').click(); pg.wait_for_timeout(3000)
        pg.get_by_text('Next: Adjust Joints').click(); pg.wait_for_timeout(3000)
        pg.get_by_role('button', name='Finish Setup').click(); pg.wait_for_timeout(8000)
        for g, (x, y) in PIV.items():
            pg.get_by_text(g, exact=True).first.click(); pg.wait_for_timeout(500)
            for idx, val in ((5, x), (6, y)):
                e = num.nth(idx); e.fill(str(val)); e.press('Enter'); pg.wait_for_timeout(200)
        for name in ('handwear-r', 'legwear-r'):
            items = pg.get_by_text(name, exact=True)
            for i in range(items.count()):
                items.nth(i).click(); pg.wait_for_timeout(400)
                pg.get_by_role('button', name='Remesh').first.click(); pg.wait_for_timeout(1500)
    else:
        pg.locator('button', has_text=re.compile('^groups$', re.I)).first.click(); pg.wait_for_timeout(800)
        expand(pg)
    for g, r in ROT:
        pg.get_by_text(g, exact=True).first.click(); pg.wait_for_timeout(500)
        e = num.nth(2); e.fill(str(r)); e.press('Enter'); pg.wait_for_timeout(400)
        print(g, 'rotation now', num.nth(2).input_value(), 'pivot', num.nth(5).input_value(), num.nth(6).input_value())
    pg.get_by_text('root', exact=True).first.click(); pg.wait_for_timeout(1500)
    pg.screenshot(path=f'{T}/st7_{tag}.png')
    b.close()
print('ok', tag)
