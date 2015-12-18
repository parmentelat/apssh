#!/usr/bin/env python3

import os, os.path
from argparse import ArgumentParser
import asyncio

from sshproxy import SshProxy

default_username = os.getlogin()
default_private_key = os.path.expanduser("~/.ssh/id_rsa")

class Scope:

    def add_parser_arguments(self, parser):
        parser.add_argument("-f", "--targets-file", dest='targets_files',
                            default=[], action='append', type=str,
                            help="Specify files that contain a list of target hosts - additive")
        parser.add_argument("-t", "--target", dest='targets',
                            default=[], action='append', type=str,
                            help="comma-separated list of target hosts - additive")
        parser.add_argument("-u", "--username", default=default_username,
                            help="remote user name - default is {}".format(default_username))
        parser.add_argument("-i", "--private-keys",
                            default=[default_private_key], action='append', type=str,
                            help="specify private key file(s) - additive - default is to use {}"
                            .format(default_private_key))

    def show(self):
        pass

    def create_proxies(self, args):
        # gather targets as mentioned in files and on the command line
        # always assume they can be comma-separated
        targets = []
        # read input file(s)
        if args.targets_files:
            for targets_file in args.targets_files:
                try:
                    with open(targets_file) as input:
                        for line in input:
                            line = line.strip()
                            if line.startswith('#'): continue
                            line = line.split()
                            for token in line:
                                targets += token.split(',')
                except IOError as e:
                    print("Could not open file {} - aborting".format(self.targets_files))
        # add command line targets
        for target in args.targets:
            targets += target.split(',')

        # create tuples username, hostname
        # use the username if already present in the target,
        # otherwise the one specified with --username
        def user_host(target):
            try:
                user, hostname = target.split('@')
                return user, hostname
            except:
                return args.username, target

        # create proxies
        return ( SshProxy(hostname, username=username, client_keys=args.private_keys)
                 for username, hostname in  (user_host(target) for target in targets))

def main():
    parser = ArgumentParser()
    scope = Scope()
    scope.add_parser_arguments(parser)
    parser.add_argument("commands", nargs='+', type=str,
                            help="command to run remotely")
    args = parser.parse_args()
    proxies = scope.create_proxies(args)

    tmp_proxies = list(proxies)

    command = " ".join(args.commands)
    tasks = [proxy.connect_and_run(command) for proxy in tmp_proxies]

    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(asyncio.gather(*tasks))

    print("END: {} proxies and {} results".format(len(tmp_proxies), len(results)))
    for proxy, result in zip(tmp_proxies, results):
        print("{} => {}".format(proxy,result), end='')
    
    return 0

if __name__ == '__main__':
    main()
