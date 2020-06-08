import asyncio

from aioquic.quic.connection import QuicConnection
from aioquic.h3.connection import H3Connection

class H3Protocol:
    def __init__(self,
    quic: QuicConnection,
    ) -> None:
        self.connection = H3Connection(quic)
