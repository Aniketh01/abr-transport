import argparse
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', '-i', help='Input dir')
    parser.add_argument('--output', '-o', help='Output dir')
    args = parser.parse_args()

    check_and_create(args.output)

    out_dir = get_out_dir(args.input)
    for folder in out_dir:
        files = glob(folder + "/" + "frame-*")
        for file in files:
            shutil.copy2(file, args.output)


if __name__ == "__main__":
    main()