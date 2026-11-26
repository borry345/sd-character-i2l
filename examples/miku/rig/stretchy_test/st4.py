"""Bend test in Stretchy: bounds rig, set joint pivots from our rig.json test bones, rotate, screenshot.
Stretchy groups are character-side: leftArm/leftElbow/leftLeg/leftKnee = image right = our *_r."""
import os, sys
from playwright.sync_api import sync_playwright
T = os.path.dirname(os.path.abspath(__file__))
psd, tag = sys.argv[1], sys.argv[2]
POSE = [  # group, pivot (1024 page = PSD coords), rotation
    ('rightArm', (488.3, 480), 35), ('rightElbow', (466.1, 554.8), 60),   # our l arm
    ('leftArm', (565, 480), -20), ('leftElbow', (601.7, 558.8), -50),     # our r arm
    ('leftLeg', (584.3, 621), -25), ('leftKnee', (605.3, 732.1), 45),     # our r leg
    ('rightKnee', (484.8, 721.9), -30),                                   # our l leg
]


def set_group(pg, name, piv, rot):
    pg.get_by_text(name, exact=True).first.click(); pg.wait_for_timeout(800)
    ins = pg.locator('input[type=number]')
    for idx, val in ((5, piv[0]), (6, piv[1]), (2, rot)):
        e = ins.nth(idx); e.fill(str(val)); e.press('Enter'); pg.wait_for_timeout(300)


with sync_playwright() as p:
    b = p.chromium.launch(channel='msedge', headless=True)
    pg = b.new_page(viewport={'width': 1600, 'height': 1000})
    pg.goto('https://editor.stretchy.studio', wait_until='networkidle', timeout=90000)
    pg.wait_for_timeout(2000)
    pg.locator('input[type=file]').set_input_files(psd)
    pg.wait_for_timeout(5000)
    pg.get_by_role('button', name='Continue →').click(); pg.wait_for_timeout(3000)
    pg.get_by_text('Next: Adjust Joints').click(); pg.wait_for_timeout(3000)
    pg.get_by_role('button', name='Finish Setup').click(); pg.wait_for_timeout(8000)
    for g, piv, rot in POSE:
        set_group(pg, g, piv, rot)
    pg.wait_for_timeout(2000)
    pg.get_by_text('root', exact=True).first.click(); pg.wait_for_timeout(1500)
    pg.screenshot(path=f'{T}/st_{tag}_09_bend.png')
    pg.locator('canvas').first.screenshot(path=f'{T}/st_{tag}_09_bend_canvas.png')
    b.close()
print('ok')
