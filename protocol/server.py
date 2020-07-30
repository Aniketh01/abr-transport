import asyncio
import os
from functools import partial
from typing import Callable, Dict, Optional, Text, Union, cast

from aioquic.buffer import Buffer
from aioquic.quic.connection import NetworkAddress, QuicConnection
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.retry import QuicRetryTokenHandler
from aioquic.tls import SessionTicketHandler, SessionTicketFetcher
from .socketFactory import QuicFactorySocket, QuicStreamHandler

from aioquic.quic.packet import (
    PACKET_TYPE_INITIAL,
    pull_quic_header,
    encode_quic_retry,
    encode_quic_version_negotiation,
)

class QuicServer(asyncio.DatagramProtocol):
    def __init__(
        self,
        *,
        configuration: QuicConfiguration,
        create_protocol: Callable = QuicFactorySocket,
        session_ticket_fetcher: Optional[SessionTicketFetcher] = None,
        session_ticket_handler: Optional[SessionTicketHandler] = None,
        retry: bool = False,
        stream_handler: Optional[QuicStreamHandler] = None,
    ) -> None:
        self._configuration = configuration
        self._create_protocol = create_protocol
        self._loop = asyncio.get_event_loop()
        self._protocols: Dict[bytes, QuicFactorySocket] = {}
        self._session_ticket_fetcher = session_ticket_fetcher
        self._session_ticket_handler = session_ticket_handler
        self._transport: Optional[asyncio.DatagramProtocol] = None

        self._stream_handler = stream_handler

        if retry:
            self._retry = QuicRetryTokenHandler()
        else:
            self._retry = None


    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self._transport = cast(asyncio.DatagramProtocol, transport)

    def datagram_received(self, data: Union[bytes, Text], addr: NetworkAddress) -> None:
        data = cast(bytes, data)
        buf = Buffer(data=data)

        try:
            header = pull_quic_header(
                buf, host_cid_length=self._configuration.connection_id_length
            )
        except ValueError:
            return

        # version negotiation
        if (
            header.version is not None
            and header.version not in self._configuration.supported_versions
        ):
            self._transport.sendto(
                encode_quic_version_negotiation(
                    source_cid=header.destination_cid,
                    destination_cid=header.source_cid,
                    supported_versions=self._configuration.supported_versions,
                ),
                addr,
            )
            return
        
        protocol = self._protocols.get(header.destination_cid, None)
        original_destination_connection_id: Optional[bytes] = None
        retry_source_connection_id: Optional[bytes] = None
        if (
            protocol is None
            and len(data) >= 1200
            and header.packet_type == PACKET_TYPE_INITIAL
        ):
            #retry
            if self._retry is not None:
                if not header.token:
                    # create a retry token
                    source_cid = os.urandom(8)
                    self._transport.sendto(
                        encode_quic_retry(
                            version=header.version,
                            source_cid=source_cid,
                            destination_cid =header.source_cid,
                            original_destination_cid=header.destination_cid,
                            retry_token=self._retry.create_token(
                                addr, header.destination_cid, source_cid
                            ),
                        ),
                        addr,
                    )
                    return
                else:
                    # validate retry token
                    try:
                        (original_destination_cid, retry_source_connection_id) = self._retry.validate_token(addr, header.token)
                    except ValueError:
                        return
            else:
                original_destination_connection_id = header.destination_cid
            
            # create new connection
            connection = QuicConnection(
                configuration=self._configuration,
                original_destination_connection_id=original_destination_connection_id,
                retry_source_connection_id=retry_source_connection_id,
                session_ticket_handler=self._session_ticket_handler,
                session_ticket_fetcher = self._session_ticket_fetcher,
            )

            # initiate the QuicSocketFactory class with the below call.
            protocol = self._create_protocol(
                connection, stream_handler=self._stream_handler
            )
            protocol.connection_made(self._transport)

            # register callbacks
            protocol._connection_id_issued_handler = partial(
                self._connection_id_issued, protocol=protocol
            )
            protocol._connection_id_retired_handler = partial(
                self._connection_id_retired, protocol=protocol
            )
            protocol._connection_terminated_handler = partial(
                self._connection_terminated, protocol=protocol
            )

            self._protocols[header.destination_cid] = protocol
            self._protocols[connection.host_cid] = protocol

        if protocol is not None:
            protocol.datagram_received(data, addr)

    def _connection_id_issued(self, cid: bytes, protocol: QuicFactorySocket):
        self._protocols[cid] = protocol

    def _connection_id_retired(
        self, cid: bytes, protocol: QuicFactorySocket
    ) -> None:
        assert self._protocols[cid] == protocol
        del self._protocols[cid]

    def _connection_terminated(self, protocol: QuicFactorySocket):
        for cid, proto in list(self._protocols.items()):
            if proto == protocol:
                del self._protocols[cid]


    def close(self) -> None:
        for protocol in set(self._protocols.values()):
            protocol.close()
        self._protocols.clear()
        self._transport.close()

"""
Start a QUIC server at the given `host` and `port`.
"""
async def start_server(
    host: str,
    port: int,
    *,
    configuration: QuicConfiguration,
    create_protocol: Callable = QuicFactorySocket,
    session_ticket_fetcher: Optional[SessionTicketFetcher] = None,
    session_ticket_handler: Optional[SessionTicketHandler] = None,
    retry: bool = False,
    stream_handler: QuicStreamHandler = None,
) -> QuicServer:
    loop = asyncio.get_event_loop()

    _, protocol = await loop.create_datagram_endpoint(
        lambda: QuicServer(
            configuration= configuration,
            create_protocol= create_protocol,
            session_ticket_fetcher = session_ticket_fetcher,
            session_ticket_handler = session_ticket_handler,
            retry = retry,
            stream_handler = stream_handler,
        ),
        local_addr=(host, port),
    )
    return cast(QuicServer, protocol)

