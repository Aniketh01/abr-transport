import asyncio
import socket
import ipaddress
import sys
from typing import AsyncGenerator, Callable, Optional, cast

from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.connection import QuicConnection
from aioquic.tls import SessionTicketHandler
from .compact import asynccontextmanager
from .socketFactory import QuicFactorySocket, QuicStreamHandler

__all__ = ["connect"]

@asynccontextmanager
async def connect(
    host: str,
    port: int,
    *,
    configuration: Optional[QuicConfiguration] = None,
    create_protocol: Optional[Callable] = QuicFactorySocket,
    session_ticket_handler: Optional[SessionTicketHandler] = None,
    stream_handler: Optional[QuicStreamHandler] = None,
    wait_connected: bool = True,
    local_port: int = 0,
) -> AsyncGenerator[QuicFactorySocket, None]:
    
    loop = asyncio.get_event_loop()
    local_host = "::"

    try:
        ipaddress.ip_address(host)
        server_name = None
    except ValueError:
        server_name = host
    
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_DGRAM)
    addr = infos[0][4]
    if len(addr) == 2:
        addr = ("::ffff:" + addr[0], addr[1], 0, 0)
    
    #prepare QUIC connection
    if configuration is None:
        configuration = QuicConfiguration(is_client=True)
    if server_name is not None:
        configuration.server_name = server_name
    connection = QuicConnection(
        configuration=configuration, session_ticket_handler=session_ticket_handler
    )

    _, protocol = await loop.create_datagram_endpoint(
        lambda: create_protocol(connection, stream_handler=stream_handler),
        local_addr=(local_host, local_port)
    )
    protocol = cast(QuicFactorySocket, protocol)
    protocol.connect(addr)
    if wait_connected:
        await protocol.wait_connected()
    try:
        yield protocol
    finally:
        protocol.close()
    await protocol.wait_closed()