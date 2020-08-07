# HTTP3 and QUIC

Introducing a HTTP/3 application utilzing functions/APIs provided by aioquic.

### General design idea

- A UDP socket that is used to send data between endpoints. The QUIC datagrams are layed on top of this UDP socket for communication.
- The QUIC Transport then takes the HTTP data to and fro between the endpoints.

### High level design choice

Below explains on how the abstract design hierarchy of each protocols in different layers should be: 

- The final result of QUIC transport and HTTP/3 transport should ideally be implemented as a socket that each other connect to and lay over with.
- The QUIC transport as a socket should be independent as to send datagrams indivually over it's stream without HTTP/3 support.
- The HTTP/3 transport should  utilise this QUIC socket to connect to the endpoint. 


### Project / codebase design architecture

`h3_client.py:` Implements a HTTP/3 based transport using QUIC as a download mechanism where segments/content are downloaded as GET requests.

`quic_client.py:` Implements a QUIC only transport to download segments.

`server.py`: Handles both HTTP/3 and QUIC protocol requests send over by the clients. Basically gives out the segments requested and also supports for server push.  

`config.py`: Add any pre-build default configuration that has to be set for both the network side as well as the streaming side of the code. Further, this configs are feeded into the `player.py` in case the defaults are not set or it has to be overridden.

`player.py`: Handles the construction of both the transport for the segments as well as the selection of segments using adaptive bitrate algorithm. This acts as the central entry point for the data stream. Player is the main function for the project. The player is responsible for setting the arguments and configurations and feeding it to the ABR or Tranport. 