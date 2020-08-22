import argparse
import sys
import logging
import datetime
import time
import json
from glob import glob
import os
from threading import Thread
from subprocess import call
from typing import Optional

start_time = time.time()

source = 'Big_Buck_Bunny_1080_10s_20MB.mp4'
prefix = 'dash/'
framerate = 30

frame_type = {'I-Frame': 'PICT_TYPE_I', 'P-Frame': 'PICT_TYPE_P', 'B-Frame': 'PICT_TYPE_B'}
resolutions=['640x360', '854x480', '1280x720', '1920x1080']#, '2560x1440']
bitrates=[1.5, 4, 7.5, 12]#, 24]

def load_json(path):
    with open(path) as file:
        obj = json.load(file)
    return obj


def get_segment_size(output_dir: Optional[str]):
    segment_size_list = []
    if output_dir is None:
        output_dir = prefix
    else:
        output_dir = output_dir + prefix

    for idx in range(len(resolutions)):
        sg_size_res = []
        quality = resolutions[idx].split('x')[1]
        destination = ( output_dir if output_dir else '' ) + '%s/out/' % (quality)
        files = glob(destination + '/*')
        for file in files:
            size = os.path.getsize(file)
            sg_size_res.append(size)
        segment_size_list.append(sg_size_res)

    return segment_size_list


def check_and_create(dir_path):
    if dir_path.startswith(prefix):
        dir_path = os.getcwd() + '/' + dir_path

    print ("Checking: %s" % dir_path)
    if not os.path.isdir(dir_path):
        print ('Destination directory: %s does not exist, creating one' % dir_path)
        os.mkdir(dir_path)
    else:
        print ('Found directory: %s ' % dir_path)


def encode(idx, output_dir: Optional[str]):
    quality = resolutions[idx].split('x')[1]
    destination = ( prefix if prefix else '' ) + '%s/bbb_%s_%s.mp4' % (quality, quality, framerate)
    if output_dir is not None:
        destination = output_dir + destination
    print('dest: {}'.format(destination))
    dst_dir = destination.rsplit('/', 1)[0]
    if dst_dir:
        check_and_create(dst_dir)
    
    cmd = "ffmpeg -i " + source + " -vf scale=" + resolutions[idx] + " -b:v " + str(bitrates[idx]) + "M -bufsize " + str(bitrates[idx]/2) + "M -c:v libx264 -x264opts 'keyint=60:min-keyint=60:no-scenecut' -c:a copy " + destination
    print("Encoding %s: " % cmd)
    os.system(cmd)
    print ('Done encoding %sp' % quality) 

def main_encode(output_dir: Optional[str]):
	for i in range(len(resolutions)):
		print('Starting %s thread' % resolutions[i])
		t = Thread(target=encode, args=(i,output_dir,))
		t.start()

	print ('Started all threads')


# def segmentize(in_source, dst_dir, quality):
#     print('in:%s out:%s' % (in_source, dst_dir))
#     for name, type in frame_type.items():
#         cmd = ("ffmpeg -i " + in_source + " -f image2 -vf " + """"select='eq(pict_type,""" +
#                type + """)'""" + "\" -vsync vfr " + dst_dir + "/" + name + "-" + "%03d-" + quality + "p-.png")
#         os.system(cmd)

def segmentize(in_source, dst_dir, quality):
    print('in:%s out:%s' % (in_source, dst_dir))
    call(["./decode_frame", in_source, dst_dir, quality])


def main_segmentize(output_dir: Optional[str]):
    if output_dir is None:
        output_dir = prefix
    else:
        output_dir = output_dir + prefix

    for resolution in resolutions:
        quality = resolution.split('x')[1]
        in_source = ('%s%s/bbb_%s_%s.mp4' % (output_dir, quality, quality, framerate))

        check_and_create('%s%s/out/' % (output_dir, quality))
        out_dir = '%s%s/out/' % (output_dir, quality)
        segmentize(in_source, out_dir, quality)


def prepare_mpd(
    total_duration: int,
    seg_duration: int,
    start_number: int,
    total_representation: int,
    output_dir: Optional[str]
) -> None:
    # NOTE: seg_duration in ms
    # NOTE: total_duration in s
    if seg_duration is None:
        seg_duration = 1
    if start_number is None:
        start_number = 0
    if total_duration is None:
        total_duration = 10

    bitrates_kbps = []
    resolution = []
    for b in bitrates:
        bitrates_kbps.append(b*1000)

    if total_representation is None:
        total_representation = len(bitrates_kbps)

    for res in resolutions:
        resolution.append(res.split('x')[1])

    seg_size = get_segment_size(output_dir)
    seg_size= list(map(list, zip(*seg_size)))

    manifest = {
        "segment_duration_ms": seg_duration,
        "start_number": start_number,
        "total_duration": total_duration,
        "total_segments": len(seg_size),
        "total_representation": total_representation,
        "bitrates_kbps": bitrates_kbps,
        "resolutions": resolution,
        "segment_size_bytes": seg_size
    }

    if output_dir is not None:
        filename = output_dir + 'bbb_m.json'
    else:
        filename = 'bbb_m.json'

    with open(filename, 'w') as f:
        json.dump(manifest, f, indent=4)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prefix', '-p', help='Prefix')
    parser.add_argument('--seg_duration', '-sd', help='segment duration in ms')
    parser.add_argument('--start_number', '-sn', help='Start number')
    parser.add_argument('--total_duration', '-td', help='Total duration in seconds')
    parser.add_argument('--total_representation', '-tr', help='Total number of representation')
    parser.add_argument('--action', required=True, help='Action to be performed by the script. Possible actions are: encode, segmentation, mpd')
    parser.add_argument('--fps', help="Frames per second to use for re-encoding")
    parser.add_argument('-i', '--input',
                        help='The path to the video file (required).')
    parser.add_argument(
        "--output-dir", type=str, help="write encoded/segemented/manifest file to a specific destination",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="increase logging verbosity"
    )
    args = parser.parse_args()

    global prefix
    global source
    global framerate

    if args.prefix:
        if not args.prefix.endswith('/'):
            prefix = args.prefix + '/'
        else:
            prefix = args.prefix
    else:
        print ("No prefix given")
    
    if args.input:
        source = args.input 

    if args.output_dir:
        if not args.output_dir.endswith('/'):
            args.output_dir = args.output_dir + '/'

    if args.fps:
        framerate = args.fps

    if args.verbose:
        log_event = 'manifest_creation-' + str(start_time) + '.log'
    else:
        log_event = None

    logging.basicConfig(
        filename=log_event,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    logging.debug("input: " + args.input + ", datetime: " + str(datetime.datetime.now()))

    if args.output_dir is not None:
        directory_path = args.output_dir + prefix
    else:
        directory_path = prefix

    check_and_create(directory_path)

    logging.info('Running "%s" script with arguments: prefix(%s) source(%s) fps(%s)' % (args.action, directory_path, source, framerate))

    if args.action == 'segmentation':
        main_segmentize(args.output_dir)
    elif args.action == 'encode':
        main_encode(args.output_dir)
    elif args.action == 'mpd':
        prepare_mpd(args.total_duration,
                    args.seg_duration,
                    args.start_number,
                    args.total_representation,
                    args.output_dir
        )
    else:
        print("Unknown action requested. Specify one of: encode, segmentation, mpd")


if __name__ == "__main__":
    sys.exit(main())