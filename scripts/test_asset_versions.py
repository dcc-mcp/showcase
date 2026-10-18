import hashlib
import tempfile
import unittest
from pathlib import Path
from asset_versions import version_html, game_revision

class AssetVersionTests(unittest.TestCase):
    def test_local_css_js_versions_preserve_paths_and_queries(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'code.js';p.write_bytes(b'first')
            s=version_html('<script src="../../assets/code.js?x=1#top"></script><a href="https://outside/code.js">x</a><img src="a.png">','zh/games/index.html',{'assets/code.js':str(p)})
            self.assertIn('../../assets/code.js?x=1&amp;v='+hashlib.sha256(b'first').hexdigest()[:12]+'#top',s)
            self.assertIn('https://outside/code.js',s)
            self.assertIn('src="a.png"',s)
            self.assertEqual(s,version_html(s,'zh/games/index.html',{'assets/code.js':str(p)}))
            p.write_bytes(b'second');self.assertNotEqual(s,version_html(s,'zh/games/index.html',{'assets/code.js':str(p)}))

    def test_game_revision_changes_with_shell_or_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'play';p.mkdir();(p/'shell.js').write_text('one')
            a=game_revision(tmp,'play/index.html');(p/'index.html').write_text('two')
            b=game_revision(tmp,'play/index.html');self.assertNotEqual(a,b)
            (p/'shell.js').write_text('three');self.assertNotEqual(b,game_revision(tmp,'play/index.html'))
if __name__=='__main__':unittest.main()
