#!/usr/bin/env python3
"""Fail-closed production provenance gate, not an attestation of truth.

Every selected case needs a hash-bound stage graph. No legacy bypass exists.
Run before building/uploading; this does not delete an existing deployment.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import zipfile

SCHEMA = 'dcc-showcase-ecosystem/v1'
PHASES = {'authoring', 'rendering', 'export', 'post-production'}
ROUTES = {'mcp', 'ecosystem-cli', 'ecosystem-skill'}
ARTIFACTS = {'.blend', '.glb', '.gltf', '.obj', '.fbx', '.usd', '.usda', '.usdc',
             '.hip', '.hiplc', '.sbs', '.sbsar', '.rpp', '.svg', '.xcf', '.pck',
             '.zip', '.png', '.jpg', '.jpeg', '.webp', '.mp4', '.webm', '.wav',
             '.ogg', '.mp3', '.exr', '.kdenlive', '.tscn', '.gd', '.py', '.ttf', '.otf',
             '.woff', '.woff2', '.wasm', '.html', '.js', '.css'}
# Administrative reports are reviewed evidence, not manufactured artwork.
REPORT_EXTENSIONS = {'.md', '.txt', '.log', '.json'}
HEX = re.compile(r'[0-9a-f]{64}\Z')
SOURCE = re.compile(r'https://github\.com/dcc-mcp/[A-Za-z0-9_.-]+/(?:tree|commit)/[0-9a-f]{40}(?:/[^?#]*)?\Z')

# Explicit official package ownership, not a trusted-name-prefix heuristic.
# Verified against the organization's pyproject at this immutable revision.
OFFICIAL_PYPI = {
    'dcc-mcp-blender': 'https://github.com/dcc-mcp/dcc-mcp-blender/blob/1ba474f314ea2c5c35eeadc70bcd59d15775ea83/pyproject.toml',
}
PYPI_RELEASE = re.compile(r'https://pypi\.org/project/([a-z0-9-]+)/([0-9][A-Za-z0-9.!+_-]*)/\Z')


def pinned_component(component):
    if not isinstance(component, dict) or not component.get('version'):
        return False
    source = str(component.get('source', ''))
    if SOURCE.fullmatch(source):
        return True
    release = PYPI_RELEASE.fullmatch(source)
    return bool(release and release[1] in OFFICIAL_PYPI and
                release[2] == component['version'])


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local(root, value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or any(ord(c) < 32 for c in value):
        raise ValueError('invalid repository path')
    p = Path(value)
    if p.is_absolute() or any(x in ('', '.', '..') or x.startswith('.') for x in value.split('/')):
        raise ValueError('unsafe repository path')
    target = (root / p).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError('missing or escaping repository file: ' + value)
    return target


def ref(root, value):
    if not isinstance(value, dict) or not HEX.fullmatch(str(value.get('sha256', ''))):
        raise ValueError('requires path and SHA-256')
    p = local(root, value.get('path'))
    if digest(p) != value['sha256']:
        raise ValueError('SHA-256 mismatch')
    return value['path']


def required_outputs(root, case, record=None):
    def materialized(url):
        matches = [d for d in (record or {}).get('downloads', []) if d.get('url') == url]
        if len(matches) != 1:
            raise ValueError('external production download requires one hash-bound materialized copy')
        return ref(root, matches[0].get('local'))
    base = 'docs/showcase/' + case['slug'] + '/'
    manifest = json.loads(local(root, base + 'manifest.json').read_text())
    paths = {base + f['path'] for f in manifest['files'] if f['path'] not in {'README.md', 'manifest.json', 'validation.json', 'ecosystem-production.json'}}
    def media(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ('src', 'poster', 'image') and isinstance(child, str):
                    if child.startswith(('http:', 'https:')):
                        paths.add(materialized(child))
                    else: paths.add(child)
                else: media(child)
        elif isinstance(value, list):
            for child in value: media(child)
    media([case.get('cover', {})] + case.get('results', []) + case.get('steps', []))
    for resource in case.get('resources', []):
        value = resource.get('url', '')
        if value.startswith(('http:', 'https:')):
            references = [r for r in (record or {}).get('external_links', []) if r.get('url') == value]
            downloads = [d for d in (record or {}).get('downloads', []) if d.get('url') == value]
            if references:
                if len(references) != 1 or downloads or references[0].get('kind') != 'reference' or not references[0].get('reason'):
                    raise ValueError('ambiguous or unreviewed external resource classification')
            else:
                paths.add(materialized(value))
        elif value and value not in (base + 'README.md', base + 'validation.json', base + 'manifest.json'):
            paths.add(value)
    # Use the actual demo mapping; valid playables need not have a slug directory.
    playable = root / 'play/manifest.json'
    if playable.exists():
        data = json.loads(playable.read_text())
        for demo in data.get('demos', []):
            if demo.get('case_slug') == case['slug']:
                directory = str(Path(demo['url']).parent) + '/'
                paths.add(demo['url'])
                for item in data.get('files', []):
                    if item['path'].startswith(directory): paths.add(item['path'])
    for p in paths: local(root, p)
    return paths


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def delivery_packages(root, packages, produced, source_paths):
    """Verify byte-preserving ZIP delivery, never a substitute production route."""
    if not isinstance(packages, list):
        raise ValueError('delivery_packages must be an array')
    outputs = set()
    support_suffixes = {'.md', '.txt', '.json', '.yaml', '.yml', '.py'}
    for package in packages:
        archive = ref(root, package.get('archive'))
        if archive in outputs or archive in produced or archive in source_paths:
            raise ValueError('delivery archive has another producer or duplicate declaration')
        if Path(archive).suffix.lower() != '.zip':
            raise ValueError('delivery package must be a ZIP')
        members = package.get('members')
        if not isinstance(members, list) or not members:
            raise ValueError('delivery package needs its complete member inventory')
        declared = {}
        for item in members:
            name = item.get('member')
            if (not isinstance(name, str) or not name or '\\' in name or ':' in name or
                any(ord(c) < 32 for c in name) or
                any(p in ('', '.', '..') for p in name.split('/'))):
                raise ValueError('unsafe ZIP member path')
            if name in declared:
                raise ValueError('duplicate declared ZIP member')
            source = ref(root, item.get('source'))
            kind = item.get('kind')
            if kind == 'production':
                if source not in produced and source not in source_paths:
                    raise ValueError('ZIP production member lacks verified production/upstream source')
            elif kind == 'support':
                # File format alone does not prove classification: reason and whole
                # package review are bound to the graph. Known artwork cannot hide here.
                if (Path(name).suffix.lower() not in support_suffixes and Path(name).name != 'LICENSE') or not item.get('reason'):
                    raise ValueError('ZIP support member must be source code/configuration/documentation with reviewed reason')
                if Path(source).suffix.lower() not in support_suffixes and Path(source).name != 'LICENSE':
                    raise ValueError('ZIP support member source has a production format')
                content = local(root, source).read_bytes()
                if content.startswith((b'\x89PNG', b'\xff\xd8\xff', b'GIF87a', b'GIF89a', b'RIFF',
                                       b'glTF', b'BLENDER', b'PK\x03\x04', b'OggS', b'ID3',
                                       b'fLaC', b'%PDF-', b'\x76\x2f\x31\x01')) or b'\x00' in content:
                    raise ValueError('ZIP support member contains a known binary production format')
                try:
                    text = content.decode('utf-8-sig')
                except UnicodeDecodeError as exc:
                    raise ValueError('ZIP support member must be complete UTF-8 text') from exc
                # Detect actual leading SVG/native documents, not prose/code that
                # merely mentions SVG. Unknown semantics remain a review boundary.
                leading = re.sub(r'<!--.*?-->|<\?xml.*?\?>|<!DOCTYPE[^>]*>', '', text, flags=re.S).lstrip()
                if re.match(r'<(?:svg(?=\s|/|>)|REAPER_PROJECT(?=\s|>))', leading, re.I):
                    raise ValueError('ZIP support member disguises a production document')
            else:
                raise ValueError('ZIP member needs production or support classification')
            declared[name] = item['source']
        with zipfile.ZipFile(local(root, archive)) as zipped:
            infos = zipped.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)) or set(names) != set(declared):
                raise ValueError('ZIP has duplicate, missing or extra members')
            for info in infos:
                if info.is_dir() or stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1:
                    raise ValueError('ZIP directories, symlinks and encrypted members are not delivery files')
                expected = declared[info.filename]
                path = local(root, expected['path'])
                if info.file_size != path.stat().st_size:
                    raise ValueError('ZIP member length differs from retained source')
                checksum = hashlib.sha256()
                with zipped.open(info) as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        checksum.update(block)
                if checksum.hexdigest() != expected['sha256']:
                    raise ValueError('ZIP member bytes differ from retained source')
        outputs.add(archive)
    return outputs


def validate_case(root, case):
    errors = []
    def need(condition, message):
        if not condition: errors.append(message)
    try:
        filename = 'docs/showcase/' + case['slug'] + '/ecosystem-production.json'
        record = json.loads(local(root, filename).read_text())
        need(isinstance(record, dict), 'record must be an object')
        if errors: return errors
        required = required_outputs(root, case, record)
        need(record.get('schema') == SCHEMA, 'unsupported schema')
        need(record.get('case_slug') == case['slug'], 'case slug mismatch')
        phases = record.get('phases', {})
        need(isinstance(phases, dict) and set(phases) == PHASES, 'all production phases must be accounted for')
        stages = record.get('stages', [])
        need(isinstance(stages, list) and bool(stages), 'missing production stages')
        if errors: return errors
        ids, produced, inputs, producer_index = set(), {}, [], {}
        required_evidence = {filename}
        for i, stage in enumerate(stages):
            label = f'stage[{i}]'
            if not isinstance(stage, dict):
                errors.append(label + ': expected object'); continue
            ident = stage.get('id')
            need(isinstance(ident, str) and bool(ident) and ident not in ids, label + ': missing/duplicate id')
            if isinstance(ident, str): ids.add(ident)
            need(stage.get('phase') in PHASES, label + ': unknown phase')
            need(stage.get('route') in ROUTES, label + ': non-ecosystem or unknown production route')
            component = stage.get('component', {})
            need(pinned_component(component), label + ': requires pinned official ecosystem component')
            need(stage.get('status') == 'succeeded', label + ': stage did not succeed')
            # These are preserved raw bytes, not a summary or invented transcript.
            for field in ('request', 'response', 'artifact_measurement'):
                try:
                    evidence_path = ref(root, stage.get(field))
                    need(Path(evidence_path).suffix.lower() in REPORT_EXTENSIONS, label + ': raw evidence must be a report, not a production binary')
                    required_evidence.add(evidence_path)
                except (ValueError, OSError) as exc: errors.append(f'{label}.{field}: {exc}')
            outs = stage.get('outputs', [])
            need(isinstance(outs, list) and bool(outs), label + ': missing measured outputs')
            if isinstance(outs, list):
                for output in outs:
                    try:
                        p = ref(root, output)
                        need(p not in produced, label + ': duplicate final output producer')
                        produced[p] = output['sha256']
                        producer_index[p] = i
                    except (ValueError, OSError) as exc: errors.append(f'{label}.outputs: {exc}')
            try:
                measurement = json.loads(local(root, stage['artifact_measurement']['path']).read_text())
                need(measurement.get('request_sha256') == stage['request']['sha256'] and
                     measurement.get('response_sha256') == stage['response']['sha256'] and
                     measurement.get('outputs') == outs and measurement.get('status') == 'succeeded',
                     label + ': measurement must bind this request, response and exact outputs')
            except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
                errors.append(label + ': malformed artifact measurement')
            ins = stage.get('inputs', [])
            need(isinstance(ins, list), label + ': inputs must be an array')
            if isinstance(ins, list): inputs.extend((i, value) for value in ins)
        report_paths = set()
        for report in record.get('reports', []):
            try:
                p = ref(root, report)
                need(Path(p).suffix.lower() in REPORT_EXTENSIONS and bool(report.get('reason')),
                     'non-production report classification needs permitted format and reviewed reason')
                need(p not in produced, 'report cannot also be a production output')
                report_paths.add(p)
            except (ValueError, OSError) as exc: errors.append('reports: ' + str(exc))
        source_paths = set()
        for source in record.get('external_sources', []):
            try:
                p = ref(root, source)
                need(bool(source.get('origin')) and bool(source.get('license')), 'external source needs origin and rights')
                need(p not in produced, 'external source also claims a production output: ' + p)
                source_paths.add(p)
            except (ValueError, OSError) as exc: errors.append('external_sources: ' + str(exc))
        packaged = delivery_packages(root, record.get('delivery_packages', []), produced, source_paths)
        for stage_index, value in inputs:
            try:
                p = ref(root, value)
                need(p in produced or p in source_paths, 'input lacks producer or external-source provenance: ' + p)
                if p in producer_index:
                    need(producer_index[p] < stage_index, 'input must precede consuming stage (cycle/forward reference): ' + p)
            except (ValueError, OSError) as exc: errors.append('inputs: ' + str(exc))
        for phase, disposition in phases.items():
            members = [s for s in stages if isinstance(s, dict) and s.get('phase') == phase]
            need(isinstance(disposition, dict), phase + ': phase disposition must be an object')
            if not isinstance(disposition, dict): continue
            if disposition.get('status') == 'performed':
                need(bool(members), phase + ': performed phase has no production stage')
            elif disposition.get('status') == 'not-applicable':
                need(bool(disposition.get('reason')) and not members, phase + ': inapplicability needs reason and no hidden stage')
            else: errors.append(phase + ': unknown/blocked phase')
        need(bool(required), 'no selected output inventory')
        # A cryptographic hash proves byte identity, not that a claimed call occurred.
        # Review must be explicit and bound to the exact stage graph and raw evidence.
        review = record.get('review', {})
        need(isinstance(review, dict) and review.get('status') == 'verified', 'raw calls and complete production scope require independent review')
        if isinstance(review, dict):
            try:
                review_path = ref(root, review.get('evidence'))
                required_evidence.add(review_path)
                receipt = json.loads(local(root, review_path).read_text())
                graph = {key: record.get(key) for key in ('schema', 'case_slug', 'phases', 'stages', 'external_sources', 'downloads', 'reports', 'external_links', 'delivery_packages')}
                graph['selected_outputs'] = [{'path': p, 'sha256': digest(local(root, p))} for p in sorted(required - required_evidence - report_paths)]
                need(receipt.get('production_graph_sha256') == canonical_hash(graph), 'review is stale for this production graph')
                need(receipt.get('raw_calls_verified') is True and receipt.get('all_production_steps_covered') is True,
                     'review has not verified calls and whole production scope')
                need(bool(receipt.get('reviewer')) and bool(receipt.get('reviewed_at')), 'review identity/date missing')
            except (ValueError, OSError, TypeError, AttributeError) as exc: errors.append('review.evidence: ' + str(exc))
        for path in sorted(required - required_evidence - report_paths - produced.keys() - source_paths - packaged):
            errors.append('selected output lacks ecosystem producer: ' + path)
        manifest_path = 'docs/showcase/' + case['slug'] + '/manifest.json'
        manifest = json.loads(local(root, manifest_path).read_text())
        listed = {'docs/showcase/' + case['slug'] + '/' + row['path']: row for row in manifest['files']}
        for evidence_path in sorted(required_evidence):
            need(evidence_path in listed, 'evidence is not published in case manifest: ' + evidence_path)
            if evidence_path in listed:
                need(listed[evidence_path].get('sha256') == digest(local(root, evidence_path)),
                     'published evidence hash mismatch: ' + evidence_path)
    except (ValueError, OSError, KeyError, TypeError, AttributeError, zipfile.BadZipFile) as exc:
        errors.append(str(exc))
    return errors


def validate(root):
    root = Path(root)
    try:
        collection = json.loads(local(root, 'collection.json').read_text())
        cases = collection['cases']
        if not isinstance(cases, list) or not cases: raise ValueError('no selected cases')
        errors = [f"{case.get('slug', '?')}: {problem}" for case in cases for problem in validate_case(root, case)]
        if errors: return errors
        # build_site copies the complete validated play asset set, including
        # shared runtime/cross-directory dependencies. A case graph may own a
        # shared producer/upstream source once; there is no directory loophole.
        playable = root / 'play/manifest.json'
        if playable.exists():
            data = json.loads(playable.read_text())
            covered = set()
            for case in cases:
                record = json.loads(local(root, 'docs/showcase/' + case['slug'] + '/ecosystem-production.json').read_text())
                for stage in record['stages']:
                    covered.update(ref(root, value) for value in stage['outputs'])
                covered.update(ref(root, value) for value in record.get('external_sources', []))
                covered.update(ref(root, value) for value in record.get('reports', []))
            for item in data.get('files', []):
                path = item['path']
                if path not in covered:
                    errors.append('shared playable output lacks ecosystem provenance: ' + path)
        return errors
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
        return ['ecosystem collection: ' + str(exc)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default=Path(__file__).resolve().parents[1], type=Path)
    args = parser.parse_args()
    problems = validate(args.repo)
    print(json.dumps({'schema': SCHEMA, 'status': 'blocked' if problems else 'evidence-complete',
                      'authenticity_attested': False, 'errors': problems}, indent=2))
    return int(bool(problems))


if __name__ == '__main__':
    raise SystemExit(main())
