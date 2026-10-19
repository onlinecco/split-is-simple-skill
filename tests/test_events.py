import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'skills/split-is-simple/scripts/events.py'
spec = importlib.util.spec_from_file_location('events', path)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)
SECRET = 'A' * 22

class ClientTests(unittest.TestCase):
    def test_only_canonical_or_local_origins(self):
        self.assertEqual(client.base_url('https://splitissimple.com/'), client.PRODUCTION)
        self.assertEqual(client.base_url('http://127.0.0.1:3004'), 'http://127.0.0.1:3004')
        for url in ['https://evil.example', 'https://splitissimple.com.evil.example', 'https://u:p@splitissimple.com', 'https://splitissimple.com/path', 'https://splitissimple.com?x=1']:
            with self.assertRaises(ValueError): client.base_url(url)

    def test_links_are_capabilities_not_arbitrary_fetch_targets(self):
        self.assertEqual(client.event_id(f'{client.PRODUCTION}/?event={SECRET}',client.PRODUCTION),SECRET)
        for url in [f'https://evil.example/?event={SECRET}',f'{client.PRODUCTION}/?event={SECRET}&event={SECRET}', 'abc123', 'A'*23]:
            with self.assertRaises(ValueError): client.event_id(url,client.PRODUCTION)

    def test_create_preserves_retry_key_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'event.json'; body={'name':'Trip','participants':[]};p.write_text(json.dumps(body))
            response={'id':SECRET,'url':f'{client.PRODUCTION}/?event={SECRET}','revision':1}
            with patch.object(client,'request',return_value=(201,response,{})) as request, redirect_stdout(io.StringIO()):
                self.assertEqual(client.main(['create','--file',str(p),'--request-key','fixed_random_retry_key']),0)
                args=request.call_args.args
                self.assertEqual(args[0],'POST');self.assertEqual(args[2]['Idempotency-Key'],'fixed_random_retry_key');self.assertEqual(args[3],body)

    def test_update_requires_revision_and_sends_conditional_patch(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'patch.json';p.write_text('{"name":"New title"}')
            with redirect_stderr(io.StringIO()):
                self.assertEqual(client.main(['update','--event',SECRET,'--file',str(p)]),1)
            with patch.object(client,'request',return_value=(412,{'error':'Event changed'},{})) as request, redirect_stderr(io.StringIO()):
                self.assertEqual(client.main(['update','--event',SECRET,'--revision','2','--file',str(p)]),1)
                self.assertEqual(request.call_count,1);self.assertEqual(request.call_args.args[0],'PATCH');self.assertEqual(request.call_args.args[2]['X-Event-Revision'],'2')

    def test_client_does_not_follow_redirects_or_invent_links(self):
        self.assertIsNone(client.NoRedirect().redirect_request(None,None,302,'',{},'https://evil.example'))
        with patch.object(client,'request',return_value=(200,{'id':SECRET,'url':'https://evil.example'},{})), redirect_stderr(io.StringIO()):
            self.assertEqual(client.main(['get','--event',SECRET]),1)

if __name__=='__main__': unittest.main()
