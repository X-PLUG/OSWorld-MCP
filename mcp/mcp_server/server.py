import mcp.types as types
from fastmcp import FastMCP
import json
import inspect
import argparse

from tools.package.code import CodeTools, VSCodeTools
from tools.package.google_chrome import BrowserTools
from tools.package.libreoffice_calc import CalcTools, CalcToolsPlus
from tools.package.libreoffice_impress import ImpressTools, PresentationToolsUNO
from tools.package.libreoffice_writer import WriterTools
from tools.package.vlc import VLCTools
from tools.package.os import UnifiedTools

from fastmcp.tools.tool import Tool


meta_tools = {
    CodeTools: 'code',
    VSCodeTools: 'code2',
    BrowserTools: 'google_chrome',
    CalcTools: 'libreoffice_calc',
    CalcToolsPlus: 'libreoffice_calc2',
    ImpressTools: 'libreoffice_impress',
    PresentationToolsUNO: 'libreoffice_impress2',
    WriterTools: 'libreoffice_writer',
    UnifiedTools: 'os',
    VLCTools: 'vlc',
}


def format_func_name(target_cls, method_name):
    # return method_name
    return f'{meta_tools[target_cls]}.{method_name}'


def register_tools_from_json(mcp_instance: FastMCP, tools_json, target_cls):
    tools = []

    for entry in tools_json:
        fn_info = entry.get("function", {})
        full_method_name = fn_info["name"]
        # JSON 中 name 是 "CodeTools.method" 形式
        method_name = full_method_name.split(".")[-1]

        # 从类里取出这个方法
        func = getattr(target_cls, method_name, None)
        if not func:
            print(f"Warning: method {method_name} not found in {target_cls}")
            continue
        formatted_func_name = format_func_name(target_cls, method_name)

        # 将 JSON 中的 parameters、description 传给 Tool 对象
        mcp_instance.add_tool(
            Tool.from_function(
                func,
                name=formatted_func_name
            ))
        tools.append(types.Tool(
            # name=fn_info['name'],
            name=formatted_func_name,
            description=fn_info['description'],
            inputSchema=fn_info['parameters'],
        ))

    return tools


def init_server(server_name="OSWorld"):
    mcp = FastMCP(server_name)

    tools = []
    for target_cls, name in meta_tools.items():
        apis_path = f'tools/apis/{name}.json'
        with open(apis_path, 'r', encoding='utf-8') as f:
            apis = json.load(f)
        _tools = register_tools_from_json(mcp, apis, target_cls)
        tools.extend(_tools)

    tools = sorted(tools, key=lambda x: x.name)

    async def list_tools() -> list[types.Tool]:
        return tools

    mcp._mcp_server.list_tools()(list_tools)

    return mcp


def parse_args():
    parser = argparse.ArgumentParser(description="Run OSWorld MCP server")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run MCP in debug mode (no HTTP transport)"
    )
    args = parser.parse_args()

    return args


if __name__ == "__main__":
    args = parse_args()

    mcp = init_server("OSWorld")

    if args.debug:
        # Debug mode: run with default transport (likely stdio)
        print("Running in debug mode...")
        mcp.run()
    else:
        # Normal HTTP mode
        mcp.run(
            transport='http',
            host='0.0.0.0',
            port=9292,
        )
