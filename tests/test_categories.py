import json
import os
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import scripts.build_all as b
import scripts.build_geosite_lite as s
import scripts.build_geoip_lite as g
import scripts.category_config as c
from test_build import BASE_SITES, field, site, private

def geo(code, ip=b'\x01\x02\x03\x00', prefix=24, reverse=False):
    cidr = field(1, ip) + b'\x10' + s.varint_write(prefix)
    return field(1, field(1, code.encode()) + field(2, cidr) + (b'\x18\x01' if reverse else b''))

class CategoryEdits(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / 'outputs'; self.out.mkdir()
        (self.root / c.FILES['geosite.dat']).write_text('\n'.join(BASE_SITES) + '\n')
        (self.root / c.FILES['geoip.dat']).write_text('private\n')
        self.sources = {'geosite.dat': b''.join(site(x) for x in (*BASE_SITES, 'google', 'telegram')),
                        'geoip.dat': private() + geo('ru') + geo('cn', b'\x20\x01' + b'\x00'*14, 32)}
        self.tag = 'v1'; self.downloads = []

    def download(self, url, limit):
        self.downloads.append(url)
        if url == b.RELEASE_API:
            return json.dumps({'tag_name': self.tag, 'assets': [
                {'name': n, 'id': i, 'size': len(data), 'digest': 'sha256:' + b.sha(data),
                 'browser_download_url': 'https://example.org/' + n}
                for i, (n, data) in enumerate(self.sources.items())]}).encode()
        return self.sources[url.rsplit('/', 1)[-1]]

    def run_build(self, changes=None, force=False):
        with patch.object(b, 'download', side_effect=self.download):
            return b.run(self.out, force, config_dir=self.root, changes=changes)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def assert_no_write_on_error(self, changes):
        before = self.snapshot()
        with self.assertRaises(ValueError): self.run_build(changes)
        self.assertEqual(self.snapshot(), before)

    def test_migration_same_bytes_as_existing_build(self):
        self.run_build()
        self.assertEqual((self.out/'geosite.dat').read_bytes(), s.trim(self.sources['geosite.dat'], BASE_SITES)[0])
        self.assertEqual((self.out/'geoip.dat').read_bytes(), private())

    def test_add_both_then_scheduled_check_preserves_selection_and_skips(self):
        self.run_build()
        r = self.run_build({'geosite.dat': ('geosite:Google, telegram google', ''),
                            'geoip.dat': ('geoip:RU cn', '')})
        self.assertTrue(all(x['state'] == 'updated' for x in r['files']))
        self.assertEqual(set(s.parse_geosites((self.out/'geoip.dat').read_bytes())), {'private','ru','cn'})
        self.assertEqual(set(s.parse_geosites((self.out/'geosite.dat').read_bytes())), set(BASE_SITES)|{'google','telegram'})
        before = {n: (self.out/n).read_bytes() for n in b.NAMES}
        self.downloads.clear(); r = self.run_build()
        self.assertEqual(self.downloads, [b.RELEASE_API])
        self.assertTrue(all(x['download_skipped'] for x in r['files']))
        self.assertEqual(before, {n: (self.out/n).read_bytes() for n in b.NAMES})

    def test_add_then_remove_restores_original_bytes(self):
        self.run_build(); original = {n: (self.out/n).read_bytes() for n in b.NAMES}
        self.run_build({'geosite.dat': ('google', ''), 'geoip.dat': ('ru cn', '')})
        self.run_build({'geosite.dat': ('', 'google'), 'geoip.dat': ('', 'ru cn')})
        self.assertEqual(original, {n: (self.out/n).read_bytes() for n in b.NAMES})
        self.assertTrue(all(x['download_skipped'] for x in self.run_build()['files']))

    def test_only_changed_database_downloaded(self):
        self.run_build(); self.downloads.clear()
        self.run_build({'geosite.dat': ('telegram','')})
        self.assertEqual(set(self.downloads), {b.RELEASE_API, 'https://example.org/geosite.dat'})
        self.downloads.clear(); self.run_build({'geoip.dat': ('ru','')})
        self.assertEqual(set(self.downloads), {b.RELEASE_API, 'https://example.org/geoip.dat'})

    def test_new_release_updates_contents_and_keeps_manual_selection(self):
        self.run_build({'geosite.dat': ('google',''), 'geoip.dat': ('ru','')})
        self.tag = 'v2'
        self.sources['geosite.dat'] = self.sources['geosite.dat'].replace(b'example.org', b'changed.org')
        self.sources['geoip.dat'] = private() + geo('ru', prefix=16) + geo('cn')
        self.run_build()
        for name in b.NAMES:
            source = s.parse_geosites(self.sources[name])
            actual = s.parse_geosites((self.out/name).read_bytes())
            self.assertEqual(actual, {k: source[k] for k in c.selections(self.root)[name]})

    def test_unknown_site_leaves_all_files_unchanged(self):
        self.run_build(); self.assert_no_write_on_error({'geosite.dat': ('typo',''), 'geoip.dat': ('ru','')})

    def test_unknown_ip_leaves_all_files_unchanged(self):
        self.run_build(); self.assert_no_write_on_error({'geosite.dat': ('google',''), 'geoip.dat': ('typo','')})

    def test_conflicting_add_remove_fails_before_network(self):
        self.run_build(); self.downloads.clear()
        self.assert_no_write_on_error({'geoip.dat': ('ru','ru')})
        self.assertEqual(self.downloads, [])

    def test_empty_result_fails_before_network(self):
        self.run_build(); self.downloads.clear()
        self.assert_no_write_on_error({'geoip.dat': ('','private')})
        self.assertEqual(self.downloads, [])

    def test_rerun_same_add_and_remove_is_idempotent(self):
        changes = {'geosite.dat': ('google','category-public-tracker'), 'geoip.dat': ('ru','cn')}
        self.run_build(changes); self.downloads.clear()
        self.run_build(changes)
        self.assertEqual(self.downloads, [b.RELEASE_API])

    def test_bad_geoip_rejects_site_change_and_config_write(self):
        self.run_build(); self.sources['geoip.dat'] += geo('bad', prefix=33)
        self.assert_no_write_on_error({'geosite.dat': ('google',''), 'geoip.dat': ('bad','')})

    def test_private_cidr_count_not_total(self):
        self.run_build({'geoip.dat': ('ru cn','')})
        meta = json.loads((self.out/'metadata'/'geoip.dat.json').read_text())
        self.assertEqual(meta['rule_count'], 3)
        self.assertEqual(meta['geoip_private_cidr_count'], 1)

    def test_shell_and_wrong_prefix_rejected(self):
        for kind, value in [('geosite', '$(touch hacked)'), ('geoip', 'ru;echo'),
                            ('geosite', 'geoip:ru'), ('geoip', 'geosite:google'),
                            ('geosite', 'google@ads'), ('geoip', '../private')]:
            with self.subTest(value=value), self.assertRaises(ValueError): c.parse(value,kind)

    def test_ipv6_limits_and_reverse_semantics(self):
        for data in (geo('v6', b'\x20\x01'+b'\x00'*14, 129), geo('ru', b'abc', 24)):
            with self.assertRaises(ValueError): g.verify_geoip(data, tuple(s.parse_geosites(data)))
        self.assertEqual(g.verify_geoip(geo('v6', b'\x20\x01'+b'\x00'*14,128), ('v6',)), {'v6':1})
        self.assertEqual(g.verify_geoip(geo('all', prefix=0, reverse=True), ('all',)), {'all':1})
        with self.assertRaises(ValueError): g.verify_geoip(private()+geo('private2', prefix=33), ('private','private2'))

    def test_missing_configuration_does_not_reset_to_defaults(self):
        self.run_build(); (self.root/c.FILES['geoip.dat']).unlink(); before=self.snapshot()
        with self.assertRaises(FileNotFoundError): self.run_build()
        self.assertEqual(before,self.snapshot())

    def test_readme_tracks_both_lists_and_failure_preserves_it(self):
        readme = self.out/'README.md'
        readme.write_text('Intro\n<!-- categories:start -->\n<!-- categories:end -->\nFooter\n')
        self.run_build({'geosite.dat': ('google',''), 'geoip.dat': ('ru cn','')})
        text = readme.read_text()
        self.assertIn('GeoSite — категорий: 4', text)
        self.assertIn('GeoIP — категорий: 3', text)
        self.assertTrue(text.startswith('Intro\n') and text.endswith('\nFooter\n'))
        self.assert_no_write_on_error({'geoip.dat': ('unknown','')})
        self.run_build()
        self.assertEqual(readme.read_text(), text)

    def test_bad_readme_markers_fail_before_writes(self):
        self.run_build()
        (self.out/'README.md').write_text('Missing markers')
        self.assert_no_write_on_error({'geoip.dat': ('ru','')})

    def test_cli_environment_then_schedule_without_inputs(self):
        argv = ['build_all.py', '--config-dir', str(self.root), '--output-dir', str(self.out)]
        env = {'GEOSITE_ADD':'geosite:google, telegram', 'GEOSITE_REMOVE':'',
               'GEOIP_ADD':'geoip:ru', 'GEOIP_REMOVE':''}
        with patch.object(sys,'argv',argv), patch.dict(os.environ,env), patch.object(b,'download',side_effect=self.download):
            b.main()
        self.assertIn('google', c.selections(self.root)['geosite.dat'])
        self.assertEqual(c.selections(self.root)['geoip.dat'], ('private','ru'))
        self.downloads.clear()
        with patch.object(sys,'argv',argv), patch.dict(os.environ,{k:'' for k in env}), patch.object(b,'download',side_effect=self.download):
            b.main()
        self.assertEqual(self.downloads, [b.RELEASE_API])

    def test_default_cli_uses_new_layout_and_reuses_metadata(self):
        config = self.out/'config'
        config.mkdir()
        for filename in c.FILES.values():
            (config/filename).write_bytes((self.root/filename).read_bytes())
        (self.out/'README.md').write_text('Intro\n<!-- categories:start -->\n<!-- categories:end -->\n')
        env = {f'{kind}_{op}'.upper(): '' for kind in ('geosite','geoip') for op in ('add','remove')}
        with patch.object(b,'ROOT',self.out), patch.object(sys,'argv',['build_all.py']), patch.dict(os.environ,env), patch.object(b,'download',side_effect=self.download):
            b.main()
            self.assertEqual({p.name for p in self.out.iterdir() if p.is_file()},
                             {'geosite.dat','geoip.dat','README.md','STATUS.md'})
            self.assertEqual({p.name for p in (self.out/'metadata').iterdir()},
                             {'geosite.dat.json','geoip.dat.json','status.json'})
            self.downloads.clear()
            b.main()
            self.assertEqual(self.downloads,[b.RELEASE_API])
