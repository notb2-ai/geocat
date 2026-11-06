import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.build_geosite_lite import varint_write
from scripts.diff_inspector import diff_file, render_diffs
from scripts import build_all


def var(num, value):
    return varint_write((num << 3) | 0) + varint_write(value)


def blob(num, value):
    return varint_write((num << 3) | 2) + varint_write(len(value)) + value


def attr(key, kind=None, value=None):
    out = blob(1, key.encode('utf-8'))
    if kind == 'bool':
        out += var(2, int(value))
    if kind == 'int':
        out += var(3, value)
    return blob(3, out)


def domain(value, kind=2, attrs=(), unknown=b''):
    body = var(1, kind) + blob(2, value.encode('utf-8'))
    body += b''.join(attr(*a) for a in attrs) + unknown
    return blob(2, body)


def geosite(categories):
    out = b''
    for category, entries in categories.items():
        out += blob(1, blob(1, category.encode()) + b''.join(entries))
    return out


def cidr(ip, prefix, unknown=b''):
    from ipaddress import ip_address
    return blob(2, blob(1, ip_address(ip).packed) + var(2, prefix) + unknown)


def geoip(categories):
    out = b''
    for category, (entries, reverse) in categories.items():
        out += blob(1, blob(1, category.encode()) + b''.join(entries) + (var(3, 1) if reverse else b''))
    return out


class DiffInspectorTests(unittest.TestCase):
    def test_domain_addition_without_count_inference(self):
        old = geosite({'yandex': [domain('old.example')]})
        new = geosite({'yandex': [domain('new.example')]})
        d = diff_file('geosite.dat', old, new)
        self.assertEqual((d['added'], d['removed']), (1, 1))
        md = '\n'.join(render_diffs([d]))
        self.assertIn('domain:new.example', md)
        self.assertIn('domain:old.example', md)
        self.assertIn('было 1, стало 1', md)

    def test_unrelated_same_category_unmodified(self):
        old = geosite({'yandex': [domain('a.example'), domain('b.example')]})
        new = geosite({'yandex': [domain('b.example'), domain('a.example')]})
        self.assertEqual(diff_file('geosite.dat', old, new)['state'], 'same_rules')

    def test_changed_rule_type(self):
        a = geosite({'yandex': [domain('example.org', 2)]})
        b = geosite({'yandex': [domain('example.org', 3)]})
        d = diff_file('geosite.dat', a, b)
        self.assertEqual((d['added'], d['removed']), (1, 1))
        r = '\n'.join(render_diffs([d]))
        self.assertIn('full:example.org', r)
        self.assertIn('domain:example.org', r)

    def test_changed_attributes(self):
        a = geosite({'yandex': [domain('example.org', attrs=[('ads', 'bool', True)])]})
        b = geosite({'yandex': [domain('example.org', attrs=[('ads', 'bool', False)])]})
        d = diff_file('geosite.dat', a, b)
        self.assertEqual((d['added'], d['removed']), (1, 1))
        r = '\n'.join(render_diffs([d]))
        self.assertIn('ads=bool:True', r)
        self.assertIn('ads=bool:False', r)

    def test_attribute_order_does_not_fake_diff(self):
        a = geosite({'yandex': [domain('example.org', attrs=[('x','bool',True),('z','int',42)])]})
        b = geosite({'yandex': [domain('example.org', attrs=[('z','int',42),('x','bool',True)])]})
        self.assertEqual(diff_file('geosite.dat', a, b)['state'], 'same_rules')

    def test_changed_subcategory_only(self):
        old=geosite({'yandex':[domain('one')], 'mailru':[domain('two')]})
        new=geosite({'yandex':[domain('one')], 'mailru':[domain('three')]})
        d=diff_file('geosite.dat',old,new)
        self.assertEqual([x['category'] for x in d['categories']], ['mailru'])

    def test_move_between_categories(self):
        old=geosite({'yandex':[domain('a'),domain('b')], 'mailru':[domain('c')]})
        new=geosite({'yandex':[domain('a')], 'mailru':[domain('c'),domain('b')]})
        d=diff_file('geosite.dat',old,new)
        self.assertEqual((d['added'], d['removed']), (1,1))
        self.assertEqual(len(d['categories']),2)

    def test_duplicates_accounted_for(self):
        old=geosite({'yandex':[domain('a'),domain('a')]})
        new=geosite({'yandex':[domain('a')]})
        d=diff_file('geosite.dat',old,new)
        self.assertEqual((d['added'],d['removed']),(0,1))

    def test_geoip_added_removed_ipv4_ipv6(self):
        old=geoip({'private':([cidr('10.0.0.0',8),cidr('2001:db8::',32)],False)})
        new=geoip({'private':([cidr('10.0.0.0',8),cidr('172.16.0.0',12)],False)})
        d=diff_file('geoip.dat',old,new)
        self.assertEqual((d['added'],d['removed']),(1,1))
        r='\n'.join(render_diffs([d]))
        self.assertIn('172.16.0.0/12',r)
        self.assertIn('2001:db8::/32',r)

    def test_geoip_reverse_changes(self):
        old=geoip({'private':([cidr('10.0.0.0',8)],False)})
        new=geoip({'private':([cidr('10.0.0.0',8)],True)})
        d=diff_file('geoip.dat',old,new)
        self.assertEqual((d['added'],d['removed']),(1,1))
        self.assertIn('[reverse]','\n'.join(render_diffs([d])))

    def test_baseline_missing(self):
        new=geosite({'a':[domain('x')]})
        self.assertEqual(diff_file('geosite.dat',b'',new)['state'],'no_baseline')

    def test_unchanged_no_extra_md_section(self):
        b=geosite({'a':[domain('x')]})
        d=diff_file('geosite.dat',b,b)
        self.assertEqual(render_diffs([d]),[])

    def test_invalid_protobuf(self):
        a=geosite({'a':[domain('x')]})
        with self.assertRaises(ValueError):diff_file('geosite.dat',a,b'\x0a\xff')

    def test_xss_escaped(self):
        a=geosite({'a':[domain('x')]})
        b=geosite({'a':[domain('<script>alert(1)</script>')]})
        text='\n'.join(render_diffs([diff_file('geosite.dat',a,b)]))
        self.assertIn('&lt;script&gt;',text)
        self.assertNotIn('<script>',text)

    def test_new_category(self):
        a=geosite({'a':[domain('x')]})
        b=geosite({'a':[domain('x')], 'b':[domain('y')]})
        d=diff_file('geosite.dat',a,b)
        self.assertEqual((d['added'],d['removed']), (1,0))

    def test_opaque_fields_are_not_ignored(self):
        a=geosite({'a':[domain('x',unknown=blob(5,b'something'))]})
        b=geosite({'a':[domain('x',unknown=blob(5,b'changed'))]})
        d=diff_file('geosite.dat',a,b)
        self.assertEqual((d['added'],d['removed']),(1,1))

    def test_render_report_without_diff_identical(self):
        report={'checked_at_moscow':'06.11.2026 06:23:00 МСК', 'files':[{'file':'geosite.dat','state':'updated'}, {'file':'geoip.dat','state':'unchanged'}]}
        expected=('# GeoCat — статус обновлений\n\nПоследняя успешная проверка: **06.11.2026 06:23:00 МСК**.\n\n'
                  '| Файл | Статус |\n|---|---|\n| geosite.dat | 🆕 Обновлён |\n| geoip.dat | ✅ Проверен — изменений нет |\n')
        self.assertEqual(build_all.render_report(report),expected)

    def test_last_change_link_survives_later_checks(self):
        report = {'checked_at_moscow': '06.11.2026 17:40:12 МСК', 'files': []}
        diffs = [
            {'file': 'geosite.dat', 'state': 'changed', 'added': 20, 'removed': 0, 'categories': []},
            {'file': 'geoip.dat', 'state': 'changed', 'added': 1, 'removed': 2, 'categories': []},
        ]
        previous = '**Последнее изменение правил:** [предыдущий отчёт](https://example.org/old)'
        env = {'GITHUB_SERVER_URL': 'https://github.com', 'GITHUB_REPOSITORY': 'owner/repo', 'GITHUB_RUN_ID': '42'}
        with patch.dict(os.environ, env):
            status = build_all.render_report(report, diffs, previous)
        expected = ('**Последнее изменение правил:** [06.11.2026 17:40:12 МСК · '
                    'GeoSite +20 · GeoIP +1 / −2](https://github.com/owner/repo/actions/runs/42)')
        self.assertIn(expected, status.splitlines())
        self.assertNotIn(previous, status)
        report['checked_at_moscow'] = '07.11.2026 08:10:00 МСК'
        for state in ('unchanged', 'same_rules', 'unavailable', 'no_baseline'):
            status = build_all.render_report(report, [{'file': 'geosite.dat', 'state': state}], status)
            self.assertEqual(status.splitlines().count(expected), 1)

    def test_diff_failure_does_not_block_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'config').mkdir();(root/'metadata').mkdir()
            (root/'config'/'geosite-categories.txt').write_text('yandex\ncategory-bank-ru\n')
            (root/'config'/'geoip-categories.txt').write_text('private\n')
            (root/'README.md').write_text('hello\n<!-- categories:start -->\n<!-- categories:end -->\n')
            site=geosite({'yandex':[domain('a')], 'category-bank-ru':[domain('b')]})
            gip=geoip({'private':([cidr('10.0.0.0',8)],False)})
            src={'geosite.dat':site,'geoip.dat':gip}
            from scripts.build_all import sha
            release={'tag_name':'202611061234','assets':[{'name':name,'size':len(data),'id':i+1,'digest':'sha256:'+sha(data),'browser_download_url':'https://test/'+name} for i,(name,data) in enumerate(src.items())]}
            def fake_download(url,max_bytes):
                return json.dumps(release).encode() if url == build_all.RELEASE_API else src[url.rsplit('/',1)[-1]]
            with patch.object(build_all,'download',side_effect=fake_download):
                with patch.object(build_all,'diff_file',side_effect=RuntimeError('fake')):
                    result=build_all.run(root,config_dir=root/'config')
            self.assertEqual(result['files'][0]['state'],'updated')
            self.assertEqual((root/'geosite.dat').read_bytes(),site)
            self.assertIn('подробное сравнение недоступно',(root/'STATUS.md').read_text())

    def test_integration_existing_count_same_new_name(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'config').mkdir();(root/'metadata').mkdir()
            (root/'config'/'geosite-categories.txt').write_text('yandex\ncategory-bank-ru\n')
            (root/'config'/'geoip-categories.txt').write_text('private\n')
            (root/'README.md').write_text('hello\n<!-- categories:start -->\n<!-- categories:end -->\n')
            old=geosite({'yandex':[domain('old')], 'category-bank-ru':[domain('b')]})
            new=geosite({'yandex':[domain('new')], 'category-bank-ru':[domain('b')]})
            gip=geoip({'private':([cidr('10.0.0.0',8)],False)})
            (root/'geosite.dat').write_bytes(old)
            (root/'geoip.dat').write_bytes(gip)
            src={'geosite.dat':new,'geoip.dat':gip}
            from scripts.build_all import sha
            release={'tag_name':'202611061234','assets':[{'name':name,'size':len(data),'id':i+1,'digest':'sha256:'+sha(data),'browser_download_url':'https://test/'+name} for i,(name,data) in enumerate(src.items())]}
            def fake_download(url,max_bytes):
                return json.dumps(release).encode() if url == build_all.RELEASE_API else src[url.rsplit('/',1)[-1]]
            with patch.object(build_all,'download',side_effect=fake_download):
                result=build_all.run(root,config_dir=root/'config')
            self.assertEqual(result['files'][0]['state'],'updated')
            self.assertEqual((root/'geosite.dat').read_bytes(),new)
            md=(root/'STATUS.md').read_text()
            self.assertIn('domain:old',md)
            self.assertIn('domain:new',md)
            self.assertIn('было 1, стало 1',md)
            self.assertEqual(json.loads((root/'metadata'/'status.json').read_text())['release'],'202611061234')

class AdditionalCases(unittest.TestCase):
    def test_zero_change_base_with_new_upstream_version(self):
        unchanged = geoip({'private': ([cidr('10.0.0.0',8)], False)})
        self.assertEqual(diff_file('geoip.dat', unchanged, unchanged)['state'],'unchanged')
    def test_empty_old_baseline(self):
        self.assertEqual(diff_file('geoip.dat', b'', geoip({'private':([cidr('10.0.0.0',8)], False)}))['state'], 'no_baseline')
    def test_removed_category(self):
        old = geosite({'a':[domain('x')], 'b':[domain('y')]})
        new = geosite({'a':[domain('x')]})
        d=diff_file('geosite.dat', old,new)
        self.assertEqual((d['added'], d['removed']), (0,1))
        self.assertEqual(d['categories'][0]['category'], 'b')
    def test_attrs_unknown_difference_displays(self):
        def weird_attr(value):
            return blob(3,blob(1,b'flag')+var(2,1)+blob(9,value))
        def raw_domain(unknown):
            return blob(2,var(1,2)+blob(2,b'a')+unknown)
        old=geosite({'a':[raw_domain(weird_attr(b'old'))]})
        new=geosite({'a':[raw_domain(weird_attr(b'new'))]})
        report='\n'.join(render_diffs([diff_file('geosite.dat', old,new)]))
        self.assertIn('6e6577',report)
        self.assertIn('6f6c64',report)
    def test_truncated_value_no_html_injection(self):
        old=geosite({'a':[domain('x')]})
        new=geosite({'a':[domain('b'*1000+'<img src=x onerror=alert(1)>')]})
        md='\n'.join(render_diffs([diff_file('geosite.dat',old,new)]))
        self.assertNotIn('<img',md)
        self.assertIn('[обрезано]',md)

if __name__=='__main__':unittest.main()
