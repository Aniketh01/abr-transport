### ABR-over-QUIC

As per the Not so QUIC: A Performance Study of DASH over QUIC, Bhat et al. TCP is more aggressive in downloading higher quality
birtrate media segments than QUIC. One of the reasons pointed out by the authors for this particular behaviour is that, the
retrofitting vanilla ABR over QUIC doesn't uses the multitude of features and enhancment QUIC provides inorder for performant
media streaming.

Hence this research is an study to optimize the retrofit of ABR over QUIC, in the hope to provide better streaming QoE by
taking advantage of useful features in QUIC.

The idea here is to "exploit"/"abuse" QUIC streams and the fact that stream IDs are cheap (they are just integers after all) to
send/receive media segments.

One (naive) example would be: every video frame you transmit is sent on a new QUIC stream. So the first I-frame is on stream 0,
the second P frame is on stream 4 (note that in QUIC stream nrs are in increments of 4), B frame on 8, etc. 
Since streams are independent of one another, you get pretty much the same out-of-order-no-hol-blocking guarantees you
get from unreliable setups.

But it is more complicated of course, because the server is still re-transmitting frames/streams that were lost. 
So, then you need to get clever with resetting/closing streams when they are no longer needed to prevent that.

Depending on the scheme, this can become hairy, as you need to get the timing right with a tradeoff between retransmission
overhead and cancelling streams too early. 


### Installing aioquic submodule to directly use it.

Try executing the below command inside the submodule:

```
$ pip install .
```

or, again within the submodule:

```
$ python3 setup.py install --user
```
