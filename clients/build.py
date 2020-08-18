import asyncio
import logging
import pickle

from urllib.parse import urlparse
from typing import Deque, Dict, List, Optional, Union, cast

from aioquic.quic.configuration import QuicConfiguration

from aioquic.tls import SessionTicket

from protocol.client import connect
from clients.quic_client import QuicClient
from clients.h3_client import HttpClient, perform_http_request


logger = logging.getLogger("Builder")

def save_session_ticket(ticket: SessionTicket) -> None:
    """
    Callback which is invoked by the TLS engine when a new session ticket
    is received.
    """
    logger.info("New session ticket received")
    if args.session_ticket:
        with open(args.session_ticket, "wb") as fp:
            pickle.dump(ticket, fp)


async def run(
    configuration: QuicConfiguration,
    urls: List[str],
    data: str,
    include: bool,
    legacy_quic: bool,
    output_dir: Optional[str],
    local_port: int,
    zero_rtt: bool,
    session_ticket: Optional[str],
) -> None:
    parsed = urlparse(urls[0])
    print(parsed)
    assert parsed.scheme in (
        "https",
        "quic",
    ), "Only https:// or quic:// URLs are supported."
    if ":" in parsed.netloc:
        host, port_str = parsed.netloc.split(":")
        port = int(port_str)
    else:
        host = parsed.netloc
        port = 443

    if session_ticket is not None:
        session_ticket = save_session_ticket
    else:
        session_ticket = None

    if legacy_quic is True:
        async with connect(
            host, port,
            configuration=configuration,
            create_protocol=QuicClient,
            wait_connected=not zero_rtt,
        ) as client:
            client = cast(QuicClient, client)
            logger.info("sending quic ack")
            await client.quic_datagram_send()
            logger.info("recieved quic ack")
            logger.info("sending quic data in stream")
            for i in range(5):
                await client.quic_stream_send()
            logger.info("recieved quic data in stream")
    else:
        async with connect(
            host,
            port,
            configuration=configuration,
            create_protocol=HttpClient,
            session_ticket_handler=session_ticket,
            local_port=local_port,
            wait_connected=not zero_rtt,
        ) as client:
            client = cast(HttpClient, client)

            coros = [
                perform_http_request(
                    client=client,
                    url=url,
                    data=data,
                    include=include,
                    output_dir = output_dir,
                )
                for url in urls
            ]

            return await asyncio.gather(*coros)


