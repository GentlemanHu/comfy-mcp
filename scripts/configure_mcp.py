import json
import os
import shutil
import sys

comfy_server_cfg = {
    "command": "/Users/gentlemanhu/.local/bin/comfy-mcp",
    "args": [],
    "env": {
        "PATH": "/Users/gentlemanhu/.local/bin:/Volumes/GodLin/Dev/Tools/Homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "COMFYUI_URL": "https://<USERNAME>:<PASSWORD>@comfy.crushing.xyz",
    },
}

# 1. Update Claude Desktop Config
desktop_cfg_path = "/Users/gentlemanhu/Library/Application Support/Claude/claude_desktop_config.json"
if os.path.exists(desktop_cfg_path):
    shutil.copyfile(desktop_cfg_path, desktop_cfg_path + ".bak")
    with open(desktop_cfg_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("mcpServers", {})["comfy"] = comfy_server_cfg
    with open(desktop_cfg_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("Updated claude_desktop_config.json")

# 2. Update ~/.claude.json
claude_json_path = "/Users/gentlemanhu/.claude.json"
if os.path.exists(claude_json_path):
    shutil.copyfile(claude_json_path, claude_json_path + ".bak")
    with open(claude_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("mcpServers", {})["comfy"] = comfy_server_cfg
    with open(claude_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("Updated ~/.claude.json")
