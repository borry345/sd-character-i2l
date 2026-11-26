"""After the wizard (bounds rig): Finish Setup, then look at the editor UI to find how to rotate a joint."""
import os, sys
from playwright.sync_api import sync_playwright
T = os.path.dirname(os.path.abspath(__file__))
psd, tag = sys.argv[1], sys.argv[2]
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
    pg.screenshot(path=f'{T}/st_{tag}_07_finished.png')
    # select the left elbow group in the layer tree, then look at the inspector
    pg.get_by_text('leftElbow', exact=True).first.click(); pg.wait_for_timeout(2000)
    pg.screenshot(path=f'{T}/st_{tag}_08_select_elbow.png')
    ins = pg.locator('input')
    print('inputs', ins.count())
    for i in range(min(ins.count(), 40)):
        e = ins.nth(i)
        try:
            print(i, e.evaluate("e => (e.type||'')+' '+(e.name||'')+' '+(e.getAttribute('aria-label')||'')+' val='+e.value+' | '+(e.closest('div')?.innerText||'').slice(0,60).replace(/\\n/g,' / ')"))
        except Exception as ex:
            print(i, 'err', ex)
    print('buttons', [t.strip()[:30] for t in pg.locator('button').all_inner_texts() if t.strip()][:50])
    b.close()
