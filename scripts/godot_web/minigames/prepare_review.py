#!/usr/bin/env python3
"""Build an artifact-only bilingual review desk from verified real production outputs."""
import argparse
import hashlib
import html
import json
import math
import re
import shutil
import subprocess
import wave
import zipfile
from pathlib import Path

from verify_candidate import verify_candidate

LANGUAGES = ('en', 'zh')
SOURCE_FILES = ('project.godot', 'game.gd', 'main.tscn', 'garden-font.otf',
                'FONT-LICENSE.txt', 'export_presets.cfg')
REQUIRED_CHECKS = {f'{lang}: garden {level} won by actual input'
                   for lang in LANGUAGES for level in (1, 2, 3)} | {
    f'{lang}: real Godot startup' for lang in LANGUAGES}


def review_instructions():
    return '''
Review desk: open /index.html or /zh/index.html on a byte-range-capable HTTP server.
Original-speed recordings and listening WAVs are under review/.
Native media seeking requires HTTP byte ranges (206 responses). Plain python -m http.server does not provide them; its game-serving instructions above do not certify media seeking.
From the dcc-mcp/showcase repository checkout, replace /path/to/minigame-site with this extracted directory and run:
python -c 'import sys; sys.path.insert(0, "scripts"); from browser_preview import QuietHandler; from functools import partial; from http.server import ThreadingHTTPServer; ThreadingHTTPServer(("127.0.0.1", 8765), partial(QuietHandler, directory="/path/to/minigame-site")).serve_forever()'
Then open http://127.0.0.1:8765/ in the review browser. This is local review only, not deployment.
No subjective listening or public release approval is implied.
'''


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def packet_timeline(path, stream):
    result = subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', stream, '-show_packets',
        '-show_data_hash', 'sha256', '-show_entries',
        'packet=data_hash,pts_time,dts_time,duration_time', '-of', 'json', str(path)], text=True)
    return json.loads(result)['packets']


def verify_packet_identity(original, remuxed):
    require(bool(original) and len(original) == len(remuxed), 'Remux changed packet count')
    for before, after in zip(original, remuxed):
        require(before.get('data_hash') == after.get('data_hash'), 'Remux changed packet bytes/order')
        for clock in ('pts_time', 'dts_time'):
            require(clock in before and clock in after and
                    abs(float(before[clock]) - float(after[clock])) < .000001,
                    'Remux changed packet timing')
        # MediaRecorder omits video packet durations. Stream copy may populate that
        # container metadata; all actual presentation/decode timestamps stay exact.
        if 'duration_time' in before:
            require('duration_time' in after and
                    abs(float(before['duration_time']) - float(after['duration_time'])) < .000001,
                    'Remux changed an existing packet duration')
    return {'packets': len(original),
            'packet_hash_sequence_sha256': hashlib.sha256(
                '\n'.join(p['data_hash'] for p in original).encode()).hexdigest(),
            'presentation_and_decode_timestamps': 'identical',
            'existing_packet_durations': 'identical'}


def remux_recording(source, target):
    # Supply duration/cues missing from MediaRecorder WebM without transcoding.
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-threads', '1', '-copyts', '-i', str(source),
                    '-map', '0:v:0', '-map', '0:a:0', '-c', 'copy',
                    '-avoid_negative_ts', 'disabled', '-y', str(target)], check=True)
    streams = {kind: verify_packet_identity(packet_timeline(source, selector),
                                           packet_timeline(target, selector))
               for kind, selector in [('video', 'v:0'), ('audio', 'a:0')]}
    meta = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
                      'format=duration', '-of', 'json', str(target)], text=True))
    seconds = float(meta['format']['duration'])
    require(math.isfinite(seconds) and seconds > 0, 'Remux lacks finite duration')
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-threads', '1', '-i', str(target),
                    '-f', 'null', '-'], check=True)
    return {'file': target.name, 'sha256': digest(target), 'raw_source_sha256': digest(source),
            'seconds': seconds, 'playback_speed': 1, 'full_decode': 'passed',
            'processing': 'Lossless stream-copy remux adds duration/cues; no re-encoding or retiming',
            'stream_identity': streams}


def original_audio(source, target):
    # No speed, pitch, gain or sample-rate filter. Keep the original channels/rate.
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-threads', '1', '-i', str(source),
                    '-map', '0:a:0', '-vn', '-c:a', 'pcm_s16le', '-y', str(target)], check=True)
    with wave.open(str(target)) as wav:
        return {'seconds': wav.getnframes() / wav.getframerate(),
                'sample_rate': wav.getframerate(), 'channels': wav.getnchannels(),
                'sample_width_bytes': wav.getsampwidth(), 'playback_speed': 1,
                'processing': 'Decoded PCM; no speed, pitch, gain or sample-rate adjustment',
                'subjective_listening': 'not-tested'}


def validate_inputs(site, native, evidence, source_commit):
    require(bool(re.fullmatch(r'[0-9a-f]{40}', source_commit)), 'Expected exact source commit')
    verify_candidate(site)
    author = json.loads((native / 'authoring.json').read_text())
    inputs = json.loads((native / 'native-input.json').read_text())
    browser = json.loads((evidence / 'verification.json').read_text())
    media = json.loads((evidence / 'media-verification.json').read_text())
    require(author.get('editor_restarted') is True, 'Native restart/reopen not established')
    require(inputs.get('passed') is True, 'Native input verification failed')
    require(browser.get('passed') is True and bool(browser.get('checks')) and
            all(c.get('passed') is True for c in browser['checks']), 'Browser verification failed')
    require(REQUIRED_CHECKS <= {c.get('name') for c in browser['checks']},
            'Incomplete real game acceptance report')
    require(browser.get('pack_sha256') == digest(site / 'play/signal-garden/game.pck'),
            'Browser report belongs to another pack')
    project = native / 'native/signal-garden'
    for name in SOURCE_FILES:
        require(author.get('native_files', {}).get(name) == digest(project / name),
                'Native source hash mismatch: ' + name)
    for name, recipe_name in [('game.gd', 'signal-garden.gd'), ('garden-font.otf', 'garden-font.otf'), ('FONT-LICENSE.txt', 'FONT-LICENSE.txt')]:
        require(digest(project / name) == digest(Path(__file__).with_name(recipe_name)),
                'Native source differs from checked-out recipe: ' + name)
    exported = json.loads((site / 'export.json').read_text())
    require(all(exported.get('source_files', {}).get(name) == digest(project / name)
                for name in SOURCE_FILES), 'Export/native source mismatch')
    require(len(media) == 2, 'Expected both language recordings')
    indexed = {row.get('file'): row for row in media}
    for lang in LANGUAGES:
        name = lang + '-native-gameplay-with-audio.mp4'
        row = indexed.get(name, {})
        require(row.get('sha256') == digest(evidence / name) and
                row.get('full_decode') == 'passed', 'Media verification mismatch: ' + lang)
        require(row.get('original_complete_recording') == lang + '-native-gameplay-with-audio.webm',
                'Unexpected original recording path')
        require(row.get('playback_speed') == 3, 'Overview speed must be explicitly labelled')
    return author, browser, indexed


COPY = {
    'en': {
        'lang': 'en', 'badge': 'UNPUBLISHED REVIEW CANDIDATE', 'title': 'Signal Garden',
        'lede': 'A quiet connection puzzle. Turn the branches. Bring three small gardens to life.',
        'play': 'Play the candidate', 'source': 'Download native source',
        'scope': 'One game · Three gardens · Native English / Chinese',
        'boundary': 'Review build only. This page does not publish a Showcase entry or grant final artistic approval.',
        'video': 'Watch the real playthrough', 'video_note': 'Original 1× canvas recording with actual game audio. Consecutive capture, without cuts; lossless remux adds seeking metadata.',
        'overview': 'Open the clearly labelled 3× overview',
        'listen': 'Listen at the original speed',
        'listen_note': 'Decoded original output, without speed, pitch, gain or sample-rate adjustment. Subjective listening is still not tested.',
        'evidence': 'What this candidate establishes',
        'verified': 'Native MCP creation, save/restart/reopen, Web export and browser input passed in this run.',
        'remaining': 'Still unverified: final visual/motion approval, subjective listening, physical phones, Safari and Firefox.',
        'checks': 'View the bounded evidence record',
        'help': 'Click or tap a tile to rotate. Arrow keys select; Space rotates; Z undoes; R resets. No timer.',
        'licenses': 'Original game source, artwork and audio: all rights reserved. Font: SIL OFL. Godot runtime notices remain included.',
    },
    'zh': {
        'lang': 'zh-CN', 'badge': '未发布 · 审查候选', 'title': '信号花园',
        'lede': '一场安静的连接谜题。转动枝条，让三座小花园慢慢亮起来。',
        'play': '试玩候选版本', 'source': '下载原生工程',
        'scope': '一个游戏 · 三个关卡 · 原生中英双语',
        'boundary': '仅供审查。本页不会发布 Showcase 作品入口，也不代表最终美术验收通过。',
        'video': '观看真实通关过程', 'video_note': '原速 1× 画布录制与实际游戏声音。连续过程无剪切；无损重封装补齐定位元数据。',
        'overview': '打开明确标注的 3× 快速预览',
        'listen': '按原速试听',
        'listen_note': '从实际输出解码，未调整速度、音高、增益或采样率。主观听感仍未验收。',
        'evidence': '本候选已经验证的范围',
        'verified': '本次原生 MCP 创作、保存重启重开、Web 导出与浏览器输入验证通过。',
        'remaining': '仍未验证：最终视觉与动态品质、主观听感、实体手机、Safari 和 Firefox。',
        'checks': '查看精简证据记录',
        'help': '点击或轻触花圃转动。方向键选择，空格旋转，Z 撤销，R 重置。没有倒计时。',
        'licenses': '原创游戏源码、美术与音频保留全部权利。字体：SIL OFL。Godot 运行时版权告知随包附带。',
    },
}


def page(lang):
    t = COPY[lang]
    prefix = '../' if lang == 'zh' else ''
    other = '../index.html' if lang == 'zh' else 'zh/index.html'
    href = lambda path: html.escape(prefix + path, quote=True)
    return f'''<!doctype html><html lang="{t['lang']}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">
<title>{t['title']} · Review candidate</title><link rel="stylesheet" href="{href('review/review.css')}"></head>
<body><main><header><span>SIGNAL GARDEN / REVIEW</span><a id="language" href="{other}" hreflang="{'en' if lang == 'zh' else 'zh-CN'}">{'English' if lang == 'zh' else '简体中文'}</a></header>
<section class="hero"><div><p class="eyebrow">{t['badge']}</p><h1>{t['title']}</h1><p class="lede">{t['lede']}</p><p>{t['scope']}</p>
<a class="button" id="play-candidate" href="{href('play/signal-garden/index.html?lang=' + lang)}">{t['play']} →</a>
<a class="download" id="source-download" href="{href('review/native-source.zip')}" download>{t['source']}</a><p class="help">{t['help']}</p></div>
<img src="{href('review/' + lang + '-start.png')}" alt="{t['title']}" width="{'720' if lang == 'zh' else '1120'}" height="{'1100' if lang == 'zh' else '780'}"></section>
<p class="notice" id="review-boundary">{t['boundary']}</p>
<section><h2>{t['video']}</h2><p>{t['video_note']}</p><video id="original-video" controls playsinline preload="metadata" poster="{href('review/' + lang + '-start.png')}" src="{href('review/' + lang + '-native-gameplay-with-audio.webm')}"></video>
<a href="{href('review/' + lang + '-native-gameplay-with-audio.mp4')}">{t['overview']}</a></section>
<section class="listen"><h2>{t['listen']}</h2><p id="listening-boundary">{t['listen_note']}</p><audio id="original-audio" controls preload="metadata" src="{href('review/' + lang + '-listening.wav')}"></audio></section>
<section><h2>{t['evidence']}</h2><p>{t['verified']}</p><p id="remaining">{t['remaining']}</p><a href="{href('review/evidence.json')}">{t['checks']}</a></section>
<footer>{t['licenses']}</footer></main></body></html>'''


def prepare(site, native, evidence, source_commit, run_id=None):
    site, native, evidence = map(lambda p: Path(p).resolve(), (site, native, evidence))
    author, browser, media = validate_inputs(site, native, evidence, source_commit)
    review = site / 'review'
    require(run_id is None or bool(re.fullmatch(r'[0-9]+', run_id)), 'Expected numeric CI run ID')
    review.mkdir()  # Refuse stale output: do not index unrelated files from an earlier build.
    audio = {}
    recordings = {}
    for lang in LANGUAGES:
        source = evidence / (lang + '-native-gameplay-with-audio.webm')
        # Inspect every source video frame and all audio, not only the shortened overview.
        subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-threads', '1', '-i', str(source),
                        '-f', 'null', '-'], check=True)
        recordings[lang] = remux_recording(source, review / source.name)
        for name in [lang + '-native-gameplay-with-audio.mp4', lang + '-start.png']:
            shutil.copyfile(evidence / name, review / name)
        target = review / (lang + '-listening.wav')
        audio[lang] = original_audio(source, target)
        require(abs(audio[lang]['seconds'] - media[lang + '-native-gameplay-with-audio.mp4']['original_seconds']) < .25,
                'Original-speed audio duration mismatch')
        audio[lang].update({'file': target.name, 'sha256': digest(target),
                           'source_sha256': digest(source), 'source_full_decode': 'passed'})
    with zipfile.ZipFile(review / 'native-source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in SOURCE_FILES:
            archive.write(native / 'native/signal-garden' / name, 'signal-garden/' + name)
        archive.writestr('signal-garden/README.txt', 'Signal Garden: one game, three gardens.\nOpen project.godot in Godot 4.6.3. Original game source, artwork and generated audio: copyright 2026 dcc-mcp contributors, all rights reserved. Garden Subset font: SIL OFL, see FONT-LICENSE.txt.\nReview candidate only; subjective listening and final artistic acceptance are not established.\n')
    shutil.copyfile(Path(__file__).with_name('review.css'), review / 'review.css')
    bounded = {'schema_version': 1, 'source_commit': source_commit,
               'commit_basis': 'Supplied by the workflow exact-head checkout; native recipe bytes checked separately',
               'scope': 'Unpublished review candidate: one game, three gardens',
               'publication': 'not-requested', 'visual_motion_review': 'not-tested',
               'subjective_listening': 'not-tested', 'physical_phone': 'not-tested',
               'safari': 'not-tested', 'firefox': 'not-tested',
               'production_date': author['date'],
               'ci_run': 'https://github.com/dcc-mcp/showcase/actions/runs/' + run_id if run_id else None,
               'artifact_retention_days': 14,
               'artifact_note': 'Temporary CI review artifact, not a permanent published resource',
               'versions': {k: author[k] for k in ('godot', 'adapter', 'core')},
               'native_restarted': True, 'native_files': {n: author['native_files'][n] for n in SOURCE_FILES},
               'pack_sha256': browser['pack_sha256'], 'browser': browser['browser'],
               'browser_checks_passed': len(browser['checks']),
               'browser_diagnostics_count': len(browser.get('diagnostics', [])),
               'diagnostics_note': 'Consult the separate raw CI report; a pass is not an error-free-log claim.',
               'audio': audio, 'recordings': recordings,
               'files': {p.name: {'bytes': p.stat().st_size, 'sha256': digest(p)}
                         for p in sorted(review.iterdir()) if p.is_file() and p.name != 'evidence.json'}}
    (review / 'evidence.json').write_text(json.dumps(bounded, indent=2, ensure_ascii=False) + '\n')
    (site / 'index.html').write_text(page('en'))
    (site / 'zh').mkdir(exist_ok=True)
    (site / 'zh/index.html').write_text(page('zh'))
    readme = site / 'README.txt'
    readme.write_text(readme.read_text() + review_instructions())
    return bounded


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--run-id')
    args = parser.parse_args()
    print(json.dumps(prepare(args.site, args.native, args.evidence, args.source_commit, args.run_id), indent=2))
