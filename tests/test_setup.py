import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('inator_setup',ROOT/'scripts/setup.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def test_mcp_config_preserves_other_servers_and_rejects_conflicting_entry(self):
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'mcp.json';workspace=pathlib.Path(folder)/'archive'
            path.write_text(json.dumps({'mcpServers':{'existing':{'command':'example'}},'other':'keep'}))
            setup.write_config(path,workspace);first=path.read_bytes();setup.write_config(path,workspace)
            self.assertEqual(path.read_bytes(),first)
            value=json.loads(first);self.assertEqual(value['other'],'keep');self.assertEqual(value['mcpServers']['existing'],{'command':'example'})
            self.assertIn(str(workspace),value['mcpServers']['gold-workspace']['args'])
            with self.assertRaises(ValueError):setup.write_config(path,workspace/'different')
            self.assertEqual(path.read_bytes(),first)
