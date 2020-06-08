import asyncio

from aioquic.quic.configuration import QuicConfiguration
from aioquic.h3.connection import H3_ALPN

class QuicProtocol:
    def __init__(self) -> None:
        self.configuration = QuicConfiguration(alpn_protocols=H3_ALPN, is_client=True)
        