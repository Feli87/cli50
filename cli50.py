#!/usr/bin/env python

import argparse
import distutils.spawn
import os
import pkg_resources
import re
import signal
import subprocess
import sys


# Require python 2.7
if sys.version_info < (2, 7):
    sys.exit("CS50 CLI requires Python 2.7 or higher")
if sys.version_info < (3, 0):
    input = raw_input

# Get distribution
try:
    __version__ = pkg_resources.get_distribution(module.__name__).version
except:
    __version__ = "UNKNOWN"


def main():

    # Listen for ctrl-c
    signal.signal(signal.SIGINT, handler)

    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--fast", action="store_true", help="skip autoupdate")
    parser.add_argument("-g", "--git", action="store_true", help="mount .gitconfig")
    parser.add_argument("-s", "--ssh", action="store_true", help="mount .ssh")
    parser.add_argument("-t", "--tag", default="latest",
                        help="start cs50/cli:TAG, else cs50/cli:latest", metavar="TAG")
    parser.add_argument("-V", "--version", action="version",
                        version="%(prog)s {}".format(__version__))
    parser.add_argument("directory", default=os.getcwd(), metavar="DIRECTORY",
                        nargs="?", help="directory to mount, else $PWD")
    args = vars(parser.parse_args())

    # Check for docker
    if not distutils.spawn.find_executable("docker"):
        parser.error("Docker not installed.")

    # Ensure directory exists
    directory = os.path.realpath(args["directory"])
    if not os.path.isdir(directory):
        parser.error("{}: no such directory".format(args["directory"]))

    # Image to use
    image = "cs50/cli:{}".format(args["tag"])

    # Update image
    if not args["fast"]:
        try:
            subprocess.check_call(["docker", "pull", image])
        except subprocess.CalledProcessError:
            sys.exit(1)

    # Check for running containers
    try:
        stdout = subprocess.check_output([
            "docker", "ps",
            "--all",
            "--filter",
            "volume={}".format(directory),
            "--format", "{{.ID}}\t{{.Image}}\t{{.RunningFor}}\t{{.Status}}"
        ]).decode("utf-8")
    except subprocess.CalledProcessError:
        sys.exit(1)
    else:
        containers = []
        for line in stdout.rstrip().splitlines():
            ID, Image, RunningFor, Status = line.split("\t")
            if Image == image and Status.startswith("Up"):
                containers.append((ID, RunningFor.lower()))

    # Ask whether to use a running container
    if containers:
        print("{} is already mounted in {} {}.".format(directory, len(
            containers), "containers" if len(containers) > 1 else "container"))
    for ID, RunningFor in containers:
        while True:
            stdin = input("New shell in {}, running for {}? [Y] ".format(ID, RunningFor))
            if re.match("^\s*(?:y|yes)?\s*$", stdin, re.I):
                try:
                    subprocess.check_call([
                        "docker", "exec",
                        "--interactive",
                        "--tty",
                        ID,
                        "bash",
                        "--login"
                    ])
                except subprocess.CalledProcessError:
                    sys.exit(1)
                else:
                    sys.exit(0)
            else:
                break

    # Options
    options = ["--detach",
               "--publish-all",
               "--rm",
               "--security-opt", "seccomp=unconfined",  # https://stackoverflow.com/q/35860527#comment62818827_35860527
               "--volume", directory + ":/home/ubuntu/workspace",
               "--workdir", "/home/ubuntu/workspace"]

    # Mount ~/.gitconfig read-only, if exists
    if args["git"]:
        gitconfig = os.path.join(os.path.expanduser("~"), ".gitconfig")
        if not os.path.isfile(gitconfig):
            sys.exit("{}: no such directory".format(gitconfig))
        options += ["--volume", "{}:/home/ubuntu/.gitconfig:ro".format(gitconfig)]

    # Mount ~/.ssh read-only, if exists
    if args["ssh"]:
        ssh = os.path.join(os.path.expanduser("~"), ".ssh")
        if not os.path.isdir(ssh):
            sys.exit("{}: no such directory".format(ssh))
        options += ["--volume", "{}:/home/ubuntu/.ssh:ro".format(ssh)]

    # Mount directory in new container
    try:

        # Run container
        id = subprocess.check_output(["docker", "run"] + options +
                                     [image, "sleep", "infinity"]).strip()

        # Display port mappings
        print(subprocess.check_output(["docker", "port", id]).strip())

        # Spawn login shell in container
        subprocess.check_call([
            "docker", "exec",
            "--interactive",
            "--tty",
            id,
            "bash",
            "--login"
        ])

        # Stop container
        subprocess.check_output(["docker", "stop", "--time", "0", id])

    except subprocess.CalledProcessError:
        sys.exit(1)
    else:
        sys.exit(0)


def handler(number, frame):
    """Handle SIGINT."""
    print("")
    sys.exit(0)


if __name__ == "__main__":
    main()
