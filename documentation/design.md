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
