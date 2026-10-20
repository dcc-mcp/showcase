"""Evidence inventory and future run contract, never a retroactive leaderboard."""
import hashlib
import json
from pathlib import Path

TRANSLATIONS = {
 '模型与评测记录': 'Models and evaluation records',
 '公开样例，不是盲测集或排行榜。缺失值保持未记录，不参与平均或排名。': 'Public examples, not a blind evaluation set or leaderboard. Missing values stay unrecorded and are not averaged or ranked.',
 '未记录': 'Not recorded', '精确模型版本': 'Exact model version',
 '运行硬件': 'Run hardware', '种子 / 尝试': 'Seed / attempt',
 '运行耗时 / 工具调用': 'Wall time / tool calls', '视觉与结构检查': 'Visual and structural checks',
 '查看原始检查与边界': 'View original checks and limits',
 '机器可读记录': 'Machine-readable records', '比较协议': 'Comparison protocol',
 '尚无符合统一协议的运行记录；历史制作归属仍保留在原有分阶段记录中。': 'No runs under a shared protocol are recorded yet; historical attribution remains in the existing stage-specific records.',
 '模型预览尚未开放：等待合格资产及完整生态证据。': 'Model preview is not enabled: eligible assets and complete ecosystem evidence are still required.',
}

def read_runs(root, cases):
    data = json.loads((Path(root) / 'benchmark/runs.json').read_text())
    if data.get('schema_version') != 1 or not isinstance(data.get('runs'), list):
        raise ValueError('benchmark: invalid run registry')
    # Enabling run publication is a distinct acceptance milestone. This pilot has no
    # benchmark-use grants, frozen protocols or accepted runs. Fail closed rather
    # than quietly present syntactically valid but unreviewed results as evidence.
    if data['runs']:
        raise ValueError('benchmark: run publication awaits protocol and rights acceptance')
    return data

def generate(root, cases):
    runs = read_runs(root, cases)
    path = Path(root) / 'collection.json'
    index = {'schema_version': 1, 'kind': 'public-showcase-inventory',
             'benchmark_accepted': False, 'usage_rights': 'not-granted-by-this-index',
             'source': {'path': 'collection.json', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()},
             'tasks': [{'case_slug': case['slug'], 'specification': {'kind': case['prompt']['kind'],
                       'source': 'collection.json#/cases/' + str(n) + '/prompt'},
                       'split': 'public-showcase', 'frozen_task_id': None, 'protocol_id': None,
                       'runs': [], 'source': case['source']} for n, case in enumerate(cases)],
             'runs': runs['runs']}
    return {'benchmark/index.json': json.dumps(index, ensure_ascii=False, indent=2)}

def section(has_preview=False):
    fields = ['精确模型版本', '运行硬件', '种子 / 尝试', '运行耗时 / 工具调用']
    rows = ''.join('<div><dt>%s</dt><dd>未记录</dd></div>' % field for field in fields)
    unavailable = '' if has_preview else '<p>模型预览尚未开放：等待合格资产及完整生态证据。</p>'
    return '''<section class="detail-section benchmark-record" id="benchmark"><h2>模型与评测记录</h2>
<p>公开样例，不是盲测集或排行榜。缺失值保持未记录，不参与平均或排名。</p>
<p>尚无符合统一协议的运行记录；历史制作归属仍保留在原有分阶段记录中。</p>
<dl>%s</dl><p><a href="#evidence">查看原始检查与边界</a> · <a href="../../benchmark/index.json">机器可读记录</a> · <a href="../../benchmark/PROTOCOL.md">比较协议</a></p>%s</section>''' % (rows, unavailable)
