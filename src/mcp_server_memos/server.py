from mcp import stdio_server
from mcp.server import Server

from .config import Config


async def new_server(config: Config) -> Server:
    server = Server()


async def serve_stdio(server: Server):
    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options, raise_exceptions=True)
