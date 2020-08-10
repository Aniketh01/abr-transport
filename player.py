import asyncio
import json
import ssl
import os
import argparse
import pickle
import logging
from typing import Deque, Dict, List, Optional, Union, cast
from urllib.parse import urlparse

try:
    import uvloop
except ImportError:
    uvloop = None


from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.quic.configuration import QuicConfiguration
from aioquic.tls import SessionTicket

from protocol.client import connect

from h3_client import HttpClient, perform_http_request
from quic_client import QuicClient
from quic_logger import QuicDirectoryLogger

import config
from adaptive.mpc import MPC

logger = logging.getLogger("DASH Player")

def save_session_ticket(ticket: SessionTicket) -> None:
    """
    Callback which is invoked by the TLS engine when a new session ticket
    is received.
    """
    logger.info("New session ticket received")
    if args.session_ticket:
        with open(args.session_ticket, "wb") as fp:
            pickle.dump(ticket, fp)

#TODO: Transport: client run() function should be central here
#TODO: Transport: The main() function should be here which takes configuration params and args
#TODO: Transport: quic only and https (with h3) only schemes should be supported with an arg switch or configs.
#TODO: Streaming: ABR functionality usage should be handled here.
#TODO: Streaming: ABR algorithm selection should be handled here using an arg switch or configs.

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
            await asyncio.gather(*coros)



if __name__ == "__main__":
    defaults = QuicConfiguration(is_client=True)
    parser = argparse.ArgumentParser(description="The player, A streaming client supporting multiple ABR options and both QUIC and HTTP/3 support")
    parser.add_argument(
        "url", type=str, nargs="+", help="the URL to query (must be HTTPS)"
    )
    parser.add_argument(
        "--manifest-file", type=str, help="Path to the custom manifest file"
    )
    parser.add_argument("--legacy-quic", action="store_true", help="use QUIC")
    parser.add_argument(
        "-k",
        "--insecure",
        action="store_true",
        help="do not validate server certificate",
    )
    parser.add_argument(
        "-d", "--data", type=str, help="send the specified data in a POST request"
    )
    parser.add_argument(
        "--ca-certs", type=str, help="load CA certificates from the specified file"
    )
    parser.add_argument(
        "--output-dir", type=str, help="write downloaded files to this directory",
    )
    parser.add_argument(
        "--local-port", type=int, default=0, help="local port to bind for connections",
    )
    parser.add_argument(
        "-s",
        "--session-ticket",
        type=str,
        help="read and write session ticket from the specified file",
    )
    parser.add_argument(
        "-q",
        "--quic-log",
        type=str,
        help="log QUIC events to QLOG files in the specified directory",
    )
    parser.add_argument(
        "--zero-rtt", action="store_true", help="try to send requests using 0-RTT"
    )
    parser.add_argument(
        "--max-data",
        type=int,
        help="connection-wide flow control limit (default: %d)" % defaults.max_data,
    )
    parser.add_argument(
        "--max-stream-data",
        type=int,
        help="per-stream flow control limit (default: %d)" % defaults.max_stream_data,
    )
    parser.add_argument(
        "-l",
        "--secrets-log",
        type=str,
        help="log secrets to a file, for use with Wireshark",
    )
    parser.add_argument(
        "-i",
        "--include",
        action="store_true",
        help="include the HTTP response headers in the output",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="increase logging verbosity"
    )
    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    if args.output_dir is not None and not os.path.isdir(args.output_dir):
        raise Exception("%s is not a directory" % args.output_dir)

    if args.manifest_file is not None:
        m_file = open(args.manifest_file)
    else:
        m_file = open(config.MANIFEST_FILE)
    manifest = json.load(m_file)

    # print(manifest)

    configuration = QuicConfiguration(
        is_client=True,
        alpn_protocols=['quic'] if args.legacy_quic else H3_ALPN,
        max_datagram_frame_size=65536
    )

    if args.ca_certs:
        configuration.load_verify_locations(args.ca_certs)
    if args.quic_log:
        configuration.quic_logger = QuicDirectoryLogger(args.quic_log)
    if args.insecure:
        configuration.verify_mode = ssl.CERT_NONE
    if args.max_data:
        configuration.max_data = args.max_data
    if args.max_stream_data:
        configuration.max_stream_data = args.max_stream_data
    if args.secrets_log:
        configuration.secrets_log_file = open(args.secrets_log, "a")
    if args.session_ticket:
        try:
            with open(args.session_ticket, "rb") as fp:
                configuration.session_ticket = pickle.load(fp)
        except FileNotFoundError:
            pass

    if uvloop is not None:
        uvloop.install()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        run(
            configuration=configuration,
            urls=args.url,
            data=args.data,
            include=args.include,
            legacy_quic=args.legacy_quic,
            output_dir=args.output_dir,
            local_port=args.local_port,
            zero_rtt=args.zero_rtt,
            session_ticket=args.session_ticket,
        )
    )

    # a = mpc.MPC(manifest)
    # # for i in range(0, 100, 10):
    # #     q = a.NextSegmentQualityIndex(10, i)
    # #     print("bitrate: {} buffer: {}".format(q, i))
    # q = a.NextSegmentQualityIndex(10)
    # print(q)