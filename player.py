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

from clients.dash_client import DashClient, perform_download
from quic_logger import QuicDirectoryLogger

import config
from adaptive.mpc import MPC
from clients.build import run

logger = logging.getLogger("DASH Player")



async def initiate_player_event(configuration: QuicConfiguration, args) -> None:
    # set rules ['bola', 'mpc']

    dc = DashClient(configuration, args)

    await dc.play()



if __name__ == "__main__":
    defaults = QuicConfiguration(is_client=True)
    parser = argparse.ArgumentParser(description="The player, A streaming client supporting multiple ABR options and both QUIC and HTTP/3 support")
    parser.add_argument(
        "--urls", type=str, nargs="+", help="the URL to query (must be HTTPS)"
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

    # Start of ABR/streaming related config parameters
    parser.add_argument("-b", "--buffer-size", action="store",
						default=60, help="Buffer size for video playback")
    parser.add_argument("--abr", "--abr", action="store", 
						default="tputRule", help="ABR rule to download video")

    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    if args.urls is None:
        logger.info("URL to download is provided by the dash client directly")

    if args.output_dir is not None and not os.path.isdir(args.output_dir):
        raise Exception("%s is not a directory" % args.output_dir)
    elif args.output_dir is None:
        args.output_dir = config.OUT_DIR

    if args.manifest_file is None:
        args.manifest_file = config.MANIFEST_FILE
    manifest = json.load(open(args.manifest_file))

    configuration = QuicConfiguration(
        is_client=True,
        alpn_protocols=['quic'] if args.legacy_quic else H3_ALPN,
        max_datagram_frame_size=65536
    )

    if args.ca_certs is None:
        args.ca_certs = config.CA_CERTS
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
        initiate_player_event(configuration=configuration, args=args)
    )

    # a = mpc.MPC(manifest)
    # # for i in range(0, 100, 10):
    # #     q = a.NextSegmentQualityIndex(10, i)
    # #     print("bitrate: {} buffer: {}".format(q, i))
    # q = a.NextSegmentQualityIndex(10)
    # print(q)