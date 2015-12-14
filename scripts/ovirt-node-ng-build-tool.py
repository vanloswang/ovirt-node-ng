#!/usr/bin/env python
#
# ovirt-node-ng-build-tool Copyright (C) 2015 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.  A copy of the GNU General Public License is
# also available at http://www.gnu.org/copyleft/gpl.html.

import argparse
import glob
import os.path
import requests
import shutil
import subprocess
import sys
import tempfile

''' Definitions of sizes
'''
KB = 1024
MB = 1024 * KB
GB = 1024 * MB

distributions = {
    'fedora23': 'https://download.fedoraproject.org/pub/fedora/linux/'
    'releases/23/Workstation/x86_64/iso/'
    'Fedora-Workstation-netinst-x86_64-23.iso',
    'centos7': 'http://mirror.centos.org/centos/7/'
    'os/x86_64/images/boot.iso'
}


def create_parser():
    '''create the parser for cmd line arguments

    >>> parser = create_parser()
    >>> parser.parse_args(["--kickstart",\
                           "ksname.ks",\
                           "out.sfs"])
    Namespace(base='centos7', disk_file='out.sfs', \
kickstart='ksname.ks', qcow_debug=False)

    >>> parser = create_parser()
    >>> parser.parse_args(["--kickstart", "appname.ks",\
                           "--base",\
                           "fedora23",\
                           "out.sfs",\
                           "--qcow-debug"])
    Namespace(base='fedora23', disk_file='out.sfs', \
kickstart='appname.ks', qcow_debug=True)
    '''

    parser = argparse.ArgumentParser(description='Parses the image to create')

    parser.add_argument('--kickstart', required=True,
                        metavar="KICKSTART",
                        help='the kickstart describing the image to create')

    parser.add_argument(
        '--base',
        required=False,
        metavar='BASE',
        default='centos7',
        help='The path to a netinstall ISO, or one of [fedora23|centos7] '
        'and the image will be retrieved automatically')

    parser.add_argument(
        '--qcow-debug',
        action='store_true',
        required=False,
        default=False,
        help="creates a qcow2 image instead of fs for debugging purposes")

    parser.add_argument('disk_file', help="the image to create",
                        metavar="DISK_FILE")

    parser.add_argument('--tmp-dir',
                        help="The temporary directory root",
                        required=False,
                        default=None,
                        type=str)

    return parser


def validate_cmdline(args):
    '''validates the arguments passed to the utility

    >>> test = {"kickstart": "ovirt-node-ng.ks",\
                "disk_file": "test.out"}
    >>> validate_cmdline(test)
    '''
    # now lets check the file exists
    if "kickstart" not in args.keys():
        raise ValueError("A required parameter is missing")
    elif not os.path.exists(args["kickstart"]):
        raise ValueError("Please provide the path to a kickstart file")

    # now lets check if the output file exists
    if "disk_file" not in args.keys():
        raise ValueError("A required parameter is missing")
    elif os.path.exists(args["disk_file"]):
        raise ValueError("The output file already exists. Stopping")

    return


def download_image(base, tmpdir):
    ''' Downloads the image for the distro or put the provided
    iso into temporary dir for future use

    >>> bootiso = download_image( 'centos7')
    >>> import os
    >>> result = os.path.exists(bootiso)
    >>> os.remove(bootiso)
    >>> print(result)
    True
    '''

    # Buffer size for downloading distro
    BUFFER_SIZE = int(1024)

    # let's create tmp file
    boot_filename = tempfile.mkstemp(prefix='ngnode',dir=tmpdir)[1]

    if base in distributions.keys():
        with open(boot_filename, 'wb') as f:
            try:
                r = requests.get(distributions[base], stream=True)
                total_length = int(r.headers.get('content-length'))
                print("Distro ISO: %s\nTotal size ISO: %s" % (
                      distributions[base], total_length))
                if not r.ok:
                    raise Exception("There was a problem downloading the "
                                    "file", exc_info=True)

                downloaded = 0
                for block in r.iter_content(BUFFER_SIZE):
                    downloaded += int(BUFFER_SIZE)
                    f.write(block)
                    percent_downloaded = int(
                        100.0 * (float(downloaded) / float(total_length))
                    )
                    sys.stdout.write("\rDownload status: [%s%%]"
                                     % percent_downloaded)

            except:
                print("There was a problem downloading the file!")
                raise

    else:
        shutil.copy2(base, boot_filename)

    return boot_filename


def main():
    parser = create_parser()
    args = parser.parse_args()
    validate_cmdline(vars(args))

    iso = download_image(args.base, args.tmp_dir)
    results = tempfile.mkdtemp(prefix='ngnode', dir=args.tmp_dir)
    os.removedirs(results)

    livemedia_creator_cmd = ['livemedia-creator',
                             '--ks', args.kickstart,
                             '--iso', iso,
                             '--resultdir', results]

    if args.qcow_debug:
        output_format = ['--make-disk', '--qcow2']
    else:
        output_format = ['--make-pxe-live']

    livemedia_creator_cmd.extend(output_format)

    if args.tmp_dir is not None:
        livemedia_creator_cmd.extend(["--tmp", args.tmp_dir])

    print("\nExecuting: %s" % livemedia_creator_cmd)

    try:
        # TODO: do something with the output?
        output = subprocess.check_call(livemedia_creator_cmd)

        img = glob.glob('{}/*.img'.format(results))[0]
        shutil.move(img, args.disk_file)

    except RuntimeError as e:
        print("Fs creation failed : {}".format(e))

    finally:
        if os.path.exists(iso):
            os.remove(iso)
        shutil.rmtree(results)


if __name__ == "__main__":
    main()

# vim: sts=4 et: