import asyncio
from fastmcp import Client
import random


class OsworldMcpClient:
    config = {
        "mcpServers": {
            "osworld_mcp": {
                "url": "http://localhost:9292/mcp",
                "transport": "streamable-http"
            },
            "filesystem": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    "/home/user",
                ]
            },
            "git": {
                "command": "uvx",
                "args": [
                    "mcp-server-git"
                ]
            }
        }
    }

    @classmethod
    def list_tools(cls, tool_name, shuffle=False, rag=True):
        async def _list_tools():
            client = Client(cls.config)
            async with client:
                tool_list = await client.list_tools()
                tool_list = [{
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                } for tool in tool_list
                ]

            if rag:
                # filter
                result = []
                for tool in tool_list:
                    if (tool_name is not None) and (tool_name in tool['name']):
                        result.append(tool)

                exclude_apps = [
                    "libreoffice_calc",
                    "libreoffice_impress",
                    "libreoffice_writer",
                    "code",
                    "vlc",
                    "google_chrome",
                    "thunderbird",
                ]
                if len(result) == 0:
                    for tool in tool_list:
                        skip = False
                        for exclude_app in exclude_apps:
                            if exclude_app in tool['name']:
                                skip = True
                        if not skip:
                            result.append(tool)
                return result

            else:
                return tool_list

        tool_list = asyncio.run(_list_tools())

        if shuffle:
            random.shuffle(tool_list)

        print(tool_list)
        return tool_list

    @classmethod
    def call_tool(cls, name, params={}):
        async def _call_tool():
            client = Client(cls.config)
            async with client:
                response = await client.call_tool(
                    name,
                    params
                )
            return response

        response = asyncio.run(_call_tool())

        print(response)
        return response


if __name__ == '__main__':
    OsworldMcpClient.call_tool(
        'VSCodeTools_search_text',
        {
            'text': 'files'
        }
    )
