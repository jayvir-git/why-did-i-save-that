"""Absolute-path launcher for MCP clients that do not set a working directory."""
import pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from gold_workspace.__main__ import main
main()
