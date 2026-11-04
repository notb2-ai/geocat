import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import scripts.build_all as b
import scripts.build_geosite_lite as s
import scripts.build_geoip_lite as g


BASE_SITES = ('yandex', 'category-bank-ru', 'category-public-tracker')

def field(n, value):
    return s.varint_write(n * 8 + 2) + s.varint_write(len(value)) + value

def site(code, value='example.org'):
    return field(1, field(1, code.encode()) + field(2, b'\x08\x02' + field(2, value.encode())))

def private(prefix=b'\x10\x08', reverse=b''):
    cidr = field(1, b'\x0a\x00\x00\x00') + prefix
    return field(1, field(1, b'PRIVATE') + field(2, cidr) + reverse)

class Builds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        (self.out/'geosite-categories.txt').write_text('\n'.join(BASE_SITES)+'\n')
        (self.out/'geoip-categories.txt').write_text('private\n')
        self.source = {'geosite.dat': b''.join(site(c) for c in BASE_SITES), 'geoip.dat': private()}
        self.release = {'tag_name':'202611031113', 'published_at':'2026-11-03T11:14:55Z', 'assets':[
            {'name':n, 'id':k, 'size':len(v), 'digest':'sha256:'+b.sha(v), 'browser_download_url':'https://example.org/'+n}
            for k,(n,v) in enumerate(self.source.items(),1)]}
        self.downloads=[]
    def download(self, url, limit):
        self.downloads.append(url)
        if url==b.RELEASE_API:return json.dumps(self.release).encode()
        return self.source[url.rsplit('/',1)[-1]]
    def run_build(self,force=False):
        with patch.object(b,'download',side_effect=self.download):return b.run(self.out,force,config_dir=self.out)
    def test_rebuild_then_skip_and_single_release_request(self):
        first=self.run_build();self.assertTrue(all(r['state']=='updated' for r in first['files']))
        self.downloads=[];second=self.run_build()
        self.assertEqual(self.downloads,[b.RELEASE_API])
        self.assertTrue(all(r['download_skipped'] and r['state']=='unchanged' for r in second['files']))
    def test_new_release_same_sources_updates_metadata_only(self):
        self.run_build();self.release['tag_name']='202611031800';self.downloads=[]
        r=self.run_build();self.assertEqual(self.downloads,[b.RELEASE_API])
        self.assertTrue(all(x['state']=='source_updated' for x in r['files']))
        self.assertEqual(json.loads((self.out/'metadata'/'geoip.dat.json').read_text())['release_tag'],'202611031800')
    def test_corrupt_local_file_rebuilt(self):
        self.run_build();(self.out/'geosite.dat').write_bytes(b'broken');r=self.run_build()
        self.assertFalse(r['files'][0]['download_skipped']);self.assertTrue(r['files'][1]['download_skipped'])
    def test_force_rebuild(self):
        self.run_build();r=self.run_build(True)
        self.assertTrue(all(not x['download_skipped'] for x in r['files']))
    def test_code_change_invalidates_cache(self):
        self.run_build()
        with patch.object(b,'fingerprint',return_value='changed'):
            r=self.run_build()
        self.assertTrue(all(not x['download_skipped'] for x in r['files']))
    def test_bad_checksum_does_not_write_either_file(self):
        self.run_build();before={str(p.relative_to(self.out)):p.read_bytes() for p in self.out.rglob('*') if p.is_file()}
        self.source['geoip.dat']=b'broken'
        with self.assertRaises(ValueError):self.run_build(True)
        self.assertEqual(before,{str(p.relative_to(self.out)):p.read_bytes() for p in self.out.rglob('*') if p.is_file()})
    def test_changed_source_same_tag_is_rebuilt(self):
        self.run_build();self.source['geosite.dat']+=site('extra')
        a=self.release['assets'][0];a['size']=len(self.source['geosite.dat']);a['digest']='sha256:'+b.sha(self.source['geosite.dat'])
        r=self.run_build();self.assertFalse(r['files'][0]['download_skipped'])
    def test_missing_category(self):
        with self.assertRaises(ValueError):s.trim(site('x'),('missing',))
    def test_truncated_and_duplicate(self):
        for data in (b'\x0a\xff',site('x')*2):
            with self.assertRaises(ValueError):s.parse_geosites(data)
    def test_varint_overflow(self):
        with self.assertRaises(ValueError):s.varint_read(b'\xff'*9+b'\x02',0,10)
    def test_private_reverse_and_default_route_rejected(self):
        self.assertEqual(g.verify_private_geoip(private()),1)
        for data in (private(reverse=b'\x18\x01'),private(prefix=b''),private(prefix=b'\x10\x00')):
            with self.assertRaises(ValueError):g.verify_private_geoip(data)
    def test_checksum_fallback(self):
        asset=copy.deepcopy(self.release['assets'][0]);asset.pop('digest')
        assets={'geosite.dat.sha256sum':{'browser_download_url':'https://example.org/sum'}}
        with patch.object(b,'download',return_value=(b.sha(self.source['geosite.dat'])+'  geosite.dat\n').encode()):
            self.assertEqual(b.expected_hash(asset,assets,'geosite.dat'),b.sha(self.source['geosite.dat']))
    def test_retry_transient_not_permanent(self):
        response=io.BytesIO(b'ok')
        with patch.object(s.urllib.request,'urlopen',side_effect=[urllib.error.URLError('temporary'),response]) as op, patch.object(s.time,'sleep'):
            self.assertEqual(s.download('https://example.org',10),b'ok');self.assertEqual(op.call_count,2)
        error=urllib.error.HTTPError('https://example.org',404,'missing',{},None)
        with patch.object(s.urllib.request,'urlopen',side_effect=error) as op:
            with self.assertRaises(urllib.error.HTTPError):s.download('https://example.org',10)
            self.assertEqual(op.call_count,1)
    def test_size_limit(self):
        with patch.object(s.urllib.request,'urlopen',return_value=io.BytesIO(b'toolong')):
            with self.assertRaises(ValueError):s.download('https://example.org',2)

if __name__=='__main__':unittest.main()
