### ABR-over-QUIC

*This is still in a work in progress state and the concepts and results related to this would be shared publicly.*

This repository is used to store information repository to the project where we try to measure and analyse the effects of video streaming, 
specifically DASH (ABR) streaming over the new generation protocol - QUIC and HTTP/3.

`protocol`: This directory contain an asyncio based implementation of quic protocol using aioquic library.
Most of the code is inspired by the library itself and being directly modified from it.

`client`: This directory contain all the client implementation classes which are referenced and used at the main entry point of the code.

`adaptive`: This directory contain the adaptive bitrate algorithm implementation for the project.

`script`: This directory contain the script related to the creation of frames and segments from video file 
and further helper scripts to produce a custom manifest file.

`tests`: This directory contain the ssl keys for the protocol.

`htdocs`: This directory contain files to test and debug the protocol.


Below, you can find the necessary steps inorder to configure this project.

### Installing aioquic submodule to directly use it.

Try executing the below command inside the submodule:

```
$ pip install .
```

or, again within the submodule:

```
$ python3 setup.py install --user
```



### Usage:

**Client**

- H3 only support client
```
python3 player.py https://localhost:4433/10 --ca-certs tests/pycacert.pem --output-dir=. --include -v
```

- QUIC only support client
```
python3 player.py https://localhost:4433/ --ca-certs tests/pycacert.pem --output-dir=. --include --legacy-quic -v
```

**Server**

```
$ python3 server.py -c tests/ssl_cert.pem -k tests/ssl_key.pem -v
```

**Move frames**

```
$ python3 move_frames.py --input ../scripts/abr/dash --output htdocs/out --action=mv_manifest
```

**How to execute the `decode_frame.c` file inside `abr-over-quic/scripts/abr`?**

```
~$ cc decode_frames.c -lstdc++ -lavcodec -lavformat -lavutil -lswresample -lswscale -o decode
```

#### Using manifest.py script for various functions

*In the order of how the execution should be done.*

**Re-encode the given input to various resolutions bitrates**

```
$ python3 manifest.py --input Big_Buck_Bunny_1080_10s_20MB.mp4 --action=encode
```

**Create segments for all the re-encoded video files**

```
$ python3 manifest.py --input Big_Buck_Bunny_1080_10s_20MB.mp4 --action=segmentation
```

**Create a custom manifest file for the tests**

```
$ python3 manifest.py --input Big_Buck_Bunny_1080_10s_20MB.mp4 --action=mpd --seg_duration=1
```