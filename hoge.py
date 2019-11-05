import sys
from pathlib import Path
from subprocess import check_output


def main():
    pf_file = Path(sys.argv[1])
    check_output(f"python ./analyzePF/apf.py parse body -s {pf_file} -t ./{pf_file.with_suffix('')}.csv", shell=True)

    csv_lines = Path(f"{pf_file.with_suffix('')}.csv").read_text().splitlines()

    result = []
    attribute_list = ["nodeidx", "recordidx", "MD5", "name", "inode", "mode_as_string", "UID", "GID", "size", "atime", "mtime", "ctime", "crtime"]
    for line in csv_lines:
        temp = {}
        for index, attr in enumerate(line.split('|')):
            temp[attribute_list[index]] = attr
        else:
            result.append(temp)


if __name__ == '__main__':
    main()

