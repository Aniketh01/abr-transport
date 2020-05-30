import argparse
from argparse import RawTextHelpFormatter
import shutil, os
from glob import glob

def check_and_create(dir_path):
    dir_path = os.getcwd() + '/' + dir_path
    print ("Checking: %s" % dir_path)
    if not os.path.isdir(dir_path):
        print ('Destination directory: %s does not exist, creating one' % dir_path)
        os.mkdir(dir_path)
    else:
        print ('Found directory: %s ' % dir_path)


def get_out_dir(dir_path):
    list_output = []
    for res_dir in os.listdir(dir_path):
        if os.path.isdir(os.path.join(dir_path, res_dir)):
            res_dir = dir_path + '/' + res_dir
            for out_dir in os.listdir(res_dir):
                out_dir = res_dir + '/' + out_dir
                if os.path.isdir(out_dir):
                    list_output.append(out_dir)
    return list_output

def move_manifest(dirpath):
    root_path = os.path.normpath(dirpath + os.sep + os.pardir)
    mpd = glob(root_path + '/' + '*.json')
    return mpd


def main():
    parser = argparse.ArgumentParser(add_help=True, formatter_class=RawTextHelpFormatter,
                                     epilog="Example usage:\n\tpython3 move_frames.py --input=directory --output=directory")
    parser.add_argument('--input', '-i', help='Input dir', required=True)
    parser.add_argument('--output', '-o', help='Output dir', required=True)
    parser.add_argument('--action', required=True, help='Action to be performed by the script. Possible actions are: mv_frame, mv_manifest')
    args = parser.parse_args()


    print ('Running "%s" script with arguments: input(%s) output(%s)' % (args.action, args.input, args.output))

    check_and_create(args.output)

    if args.action == 'mv_frame':
        print('Copying frames from %s to %s' % (args.input, args.output))
        out_dir = get_out_dir(args.input)
        for folder in out_dir:
            files = glob(folder + "/" + "frame-*")
            for file in files:
                shutil.copy2(file, args.output)
    elif args.action == 'mv_manifest':
        print('copying manifest from %s to %s' % (args.input, args.output))
        mpd = move_manifest(args.input)
        # There should be only one mpd file in the dir *always*.
        for manifest in mpd:
            shutil.copy2(manifest, args.output)

    print("DONE: Copy process complete!")

if __name__ == "__main__":
    main()
