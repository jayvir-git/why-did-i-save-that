import json,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[1]
print(json.dumps({'mcpServers':{'gold-workspace':{'command':sys.executable,'args':[str(root/'scripts/workspace.py'),'mcp']}}},indent=2))
