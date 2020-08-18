import asyncio
import os

from aioquic.quic.configuration import QuicConfiguration

from clients.build import run

import config

#TODO: Transport: client run() function should be central here and the main purpose should be to download the requested content by default.
# Also rename it to something meaningful, like perform_download() or something similar.
#TODO: Streaming: ABR functionality usage should be handled here.
#TODO: Streaming: ABR algorithm selection should be handled here using an arg switch or configs.
# The player (main entry point could pass in the args for this particular dash client to handle it's propcessing logic.)


async def perform_download(configuration: QuicConfiguration, args) -> None:
	if args.urls is None:
		args.urls = config.URLS

	res = await run(
            configuration=configuration,
            urls=args.urls,
            data=args.data,
            include=args.include,
            legacy_quic=args.legacy_quic,
            output_dir=args.output_dir,
            local_port=args.local_port,
            zero_rtt=args.zero_rtt,
            session_ticket=args.session_ticket,
        )

	print(res)


class DashClient:
	def __init__(self, configuration: QuicConfiguration, args):
		self.configuration = configuration
		self.args = args
		self.baseUrl, self.filename = os.path.split("https://localhost:4433/index.html")
	
	async def play(self) -> None:
		await perform_download(self.configuration, self.args)


# if __name__ == '__main__':
#     DashClient(10)
		