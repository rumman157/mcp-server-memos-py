from enum import Enum
from typing import Annotated

from grpclib.client import Channel
from mcp import McpError, stdio_server, types
from mcp.server import Server
from pydantic import BaseModel, Field, TypeAdapter

from .config import Config
from .proto_gen.memos.api import v1 as memos_api_v1


class Visibility(Enum):
    PUBLIC = "PUBLIC"
    PROTECTED = "PROTECTED"


class SearchMemoRequest(BaseModel):
    """Request to search memo"""

    key_word: Annotated[
        str,
        Field(
            description="""The key words to search for in the memo content.""",
        ),
    ]


class CreateMemoRequest(BaseModel):
    """Request to create memo"""

    content: Annotated[
        str,
        Field(
            description="""The content of the memo.""",
        ),
    ]
    visibility: Annotated[
        Visibility,
        Field(default=Visibility.PUBLIC, description="""The visibility of the memo."""),
    ]


class GetMemoRequest(BaseModel):
    """Request to get memo"""

    name: Annotated[
        str,
        Field(description="""The name of the memo.
Format: memos/{id}
"""),
    ]


class ListMemoTagsRequest(BaseModel):
    """Request to list memo tags"""

    parent: Annotated[
        str,
        Field(
            default="memos/-",
            description="""The parent, who owns the tags.
Format: memos/{id}. Use "memos/-" to list all tags.
""",
        ),
    ]
    visibility: Annotated[
        Visibility,
        Field(default=Visibility.PUBLIC, description="""The visibility of the tags."""),
    ]


def new_server(config: Config) -> Server:
    grpc_channel = Channel(config.host, config.port)
    memo_service = memos_api_v1.MemoServiceStub(grpc_channel)
    server = Server("mcp-server-memos")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="list_memo_tags",
                description="List all existing memo tags",
                inputSchema=ListMemoTagsRequest.model_json_schema(),
            )
        ]

    # search
    @server.call_tool()
    async def search_memo(name: str, args: dict) -> list[types.TextContent]:
        try:
            params = SearchMemoRequest.model_validate(args)
        except Exception as e:
            raise McpError(types.INVALID_PARAMS, str(e))

        req = memos_api_v1.ListMemosRequest(
            filter=f"row_status == 'NORMAL' && content_search == ['{params.key_word}']"
        )
        res = await memo_service.list_memos(list_memos_request=req)
        content = ", ".join([memo.content for memo in res.memos])
        content = f"Search result:\n{content}"
        return [types.TextContent(type="text", text=content)]

    # create
    @server.call_tool()
    async def create_memo(name: str, args: dict) -> list[types.TextContent]:
        try:
            params = CreateMemoRequest.model_validate(args)
        except Exception as e:
            raise McpError(types.INVALID_PARAMS, str(e))

        req = memos_api_v1.CreateMemoRequest(
            content=params.content,
            visibility=params.visibility.value,
        )
        res = await memo_service.create_memo(create_memo_request=req)
        content = f"Memo created: {res.id}"
        return [types.TextContent(type="text", text=content)]

    # get
    @server.call_tool()
    async def get_memo(name: str, args: dict) -> list[types.TextContent]:
        try:
            params = GetMemoRequest.model_validate(args)
        except Exception as e:
            raise McpError(types.INVALID_PARAMS, str(e))
        
        req = memos_api_v1.GetMemoRequest(name=params.name)
        res = await memo_service.get_memo(get_memo_request=req)
        content = f"Memo:\n{res.content}"
        return [types.TextContent(type="text", text=content)]

    # list tags
    @server.call_tool()
    async def list_memo_tags(name: str, args: dict) -> list[types.TextContent]:
        try:
            params = ListMemoTagsRequest.model_validate(args)
        except Exception as e:
            raise McpError(types.INVALID_PARAMS, str(e))

        req = memos_api_v1.ListMemoTagsRequest(
            parent=params.parent,
            filter=f"visibilities == ['{params.visibility.value}']",
        )
        res = await memo_service.list_memo_tags(list_memo_tags_request=req)
        content = ", ".join(res.tag_amounts.keys())
        content = f"Tags:\n{content}"
        return [types.TextContent(type="text", text=content)]

    return server


async def serve_stdio(config: Config):
    server = new_server(config)
    options = server.create_initialization_options()
    # print("serve_stdio, options:", options)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options, raise_exceptions=True)
