"""Open a saved .stretch fresh and bend: only rotations are typed (pivots and skin weights come from the file)."""
import os, sys
from playwright.sync_api import sync_playwright
T = os.path.dirname(os.path.abspath(__file__))
f, tag = sys.argv[1], sys.argv[2]
ROT = [('rightArm', 35), ('rightElbow', 60), ('leftArm', -20), ('leftElbow', -50),
       ('leftLeg', -25), ('leftKnee', 45), ('rightKnee', -30)]
with sync_playwright() as p:
    b = p.chromium.launch(channel='msedge', headless=True)
    pg = b.new_page(viewport={'width': 1600, 'height': 1000})
    pg.goto('https://editor.stretchy.studio', wait_until='networkidle', timeout=90000)
    pg.wait_for_timeout(2000)
    pg.locator('input[type=file]').set_input_files(f)
    pg.wait_for_timeout(8000)
    pg.screenshot(path=f'{T}/st_{tag}_11_opened.png')
    import re; pg.locator('button', has_text=re.compile('^groups$', re.I)).first.click(); pg.wait_for_timeout(1000)
    for _ in range(30):  # expand every collapsed group in the tree (chevron svg at rotate(0deg))
        c = pg.locator('button:has(svg[style*="rotate(0deg)"] path[d="M3 2l4 3-4 3"])')
        if c.count() == 0:
            break
        c.first.click(); pg.wait_for_timeout(200)
    num = pg.locator('input[type=number]')
    for g, r in ROT:
        pg.get_by_text(g, exact=True).first.click(); pg.wait_for_timeout(600)
        piv = (num.nth(5).input_value(), num.nth(6).input_value())
        e = num.nth(2); e.fill(str(r)); e.press('Enter'); pg.wait_for_timeout(400)
        print(g, 'pivot from file', piv, 'rot', r)
    pg.get_by_text('root', exact=True).first.click(); pg.wait_for_timeout(1500)
    pg.screenshot(path=f'{T}/st_{tag}_12_bend_from_stretch.png')
    b.close()
