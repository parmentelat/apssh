#!/usr/bin/env python3

# using the develop branch of asyncssh
import sys
sys.path.insert(0, "../asyncssh/")

import os, os.path
import time
from argparse import ArgumentParser
import asyncio

from sshproxy import SshProxy
from formatters import RawFormatter, ColonFormatter, SubdirFormatter
from window import gather_window

default_username = os.getlogin()
default_timeout = 30
default_private_key = os.path.expanduser("~/.ssh/id_rsa")

class Apssh:
    """
    Main class for apssh utility
    """

    def __init__(self):
        self.proxies = []
        self.formatter = None

    def __repr__(self):
        return "".join([str(p) for p in self.proxies])

    def read_targets_file(self, filename, debug=False):
        """
        Returns a tuple success, names
        If the provided filename exists and could be parsed, returned object will be
           True, [ name1, ...]
        Otherwise, return code is
           False, None
        """
        names = []
        try:
            with open(filename) as input:
                for line in input:
                    line = line.strip()
                    if line.startswith('#'):
                        continue
                    line = line.split()
                    for token in line:
                        names += token.split(',')
            return True, names
        except FileNotFoundError as e:
            return False, None
        except Exception as e:
            print("Unexpected exception when parsing file {}, {}".format(filename, e),
                  file=sys.stderr)
            if debug:
                import traceback
                traceback.print_exc()
            return False, None

    def create_proxies(self):
        # start with parsing excludes if any
        excludes = set()
        for exclude in self.parsed_args.excludes:
            parsed, names = self.read_targets_file(exclude)
            if parsed:
                for name in names:
                    excludes.add(name)
            else:
                excludes.add(exclude)
        if self.parsed_args.debug:
            print("Excludes = {}".format(excludes))

        # gather targets as mentioned in -t -x args
        hostnames = []
        # read input file(s)
        for target in self.parsed_args.targets:
            parsed, names = self.read_targets_file(target)
            if parsed:
                for name in names:
                    if name not in excludes:
                        hostnames.append(name)
            else:
                if target not in excludes:
                    hostnames.append(target)
        if not hostnames:
            self.parser.print_help()
            exit(1)

        if self.parsed_args.debug:
            print("Selected {} targets".format(len(hostnames)))

        # create tuples username, hostname
        # use the username if already present in the target,
        # otherwise the one specified with --username
        def user_host(target):
            try:
                user, hostname = target.split('@')
                return user, hostname
            except:
                return self.parsed_args.username, target

        # create proxies
        self.proxies = [ SshProxy(hostname, username=username,
                                  client_keys=self.parsed_args.private_keys,
                                  formatter = self.get_formatter(),
                                  debug = self.parsed_args.debug,
                                  timeout = self.parsed_args.timeout)
                         for username, hostname in  (user_host(target) for target in hostnames) ]
        return self.proxies

    def get_formatter(self):
        if self.formatter is None:
            if self.parsed_args.raw_output:
                self.formatter = RawFormatter(debug = self.parsed_args.debug)
            elif self.parsed_args.date_time:
                default_run_name = time.strftime("%Y-%m-%d@%H:%M")
                self.formatter = SubdirFormatter(default_run_name)
            elif self.parsed_args.out_dir:
                self.formatter = SubdirFormatter(self.parsed_args.out_dir)
            else:
                self.formatter = ColonFormatter()
        return self.formatter
    
    def main(self):
        self.parser = parser = ArgumentParser()
        # scope - on what hosts
        parser.add_argument("-t", "--target", dest='targets', action='append', default=[],
                            help="comma-separated list of targets (hostnames or filenames) - additive")
        parser.add_argument("-x", "--exclude", dest='excludes', action='append', default=[],
                            help="comma-separated list of excludes (hostnames or filenames) - additive")
        # major
        parser.add_argument("-w", "--window", type=int, default=0,
                            help="specify how many connections can run simultaneously; default is no limit")
        parser.add_argument("-c", "--connect-timeout", dest='timeout',
                            type=float, default=default_timeout,
                            help="specify connection timeout, default is {}s".format(default_timeout))
        # ssh settings
        parser.add_argument("-u", "--username", default=default_username,
                            help="remote user name - default is {}".format(default_username))
        parser.add_argument("-i", "--private-keys",
                            default=[default_private_key], action='append', type=str,
                            help="specify private key file(s) - additive - default is to use {}"
                            .format(default_private_key))
        # how to store results
        # xxx here xxx parser.add_argument()
        parser.add_argument("-o", "--out-dir", default=None,
                            help="specify directory where to store results")
        parser.add_argument("-d", "--date-time", default=None, action='store_true',
                            help="use date-based directory to store results")
        parser.add_argument("-r", "--raw-output", default=None, action='store_true',
                            help="produce raw result")
        parser.add_argument("-s", "--stamp", default=False, action='store_true',
                            help="""
                            available with the -d and -o options only
                            if specified, then for all nodes there will be a stamp created
                            in the output subdir, named either 0ok/<hostname> for successful nodes,
                            or 1failed/<hostname> for the other ones.
                            The stamp will contain a single line with the returned code, or 'None'
                            if the node was not reachable at all""")
        
        # turn on debugging
        parser.add_argument("-D", "--debug", action='store_true', default=False)

        # the commands to run
        parser.add_argument("commands", nargs='+', type=str, help="command to run remotely")

        args = self.parsed_args = parser.parse_args()
        proxies = self.create_proxies()
#        print(self)
        command = " ".join(args.commands)
        tasks = [ proxy.connect_and_run(command) for proxy in proxies ]

        loop = asyncio.get_event_loop()
        window = self.parsed_args.window
        if not window:
            if self.parsed_args.debug:
                print("No window limit")
            results = loop.run_until_complete(asyncio.gather(*tasks))
        else:
            if self.parsed_args.debug:
                print("Window limit={}".format(window))
            results = loop.run_until_complete(gather_window(*tasks, window=window,
                                                            debug=args.debug))

        ### print on stdout the name of the output directory
        # useful mostly with -d : 
        subdir = self.get_formatter().run_name \
                 if isinstance(self.get_formatter(), SubdirFormatter) \
                    else None
        if subdir:
            print(subdir)
        ### details on the individual retcods
        # raw
        if self.parsed_args.debug:
            for p, s in zip(proxies, results):
                print("PROXY {} -> {}".format(p.hostname, s))
        # stamps
        names = { 0 : '0ok', None : '1failed'}
        if subdir and self.parsed_args.stamp:
            # do we need to create the subdirs
            need_ok = [s for s in results if s==0]
            if need_ok:
                os.makedirs("{}/{}".format(subdir, names[0]), exist_ok=True)
            need_fail = [s for s in results if s!=0]
            if need_fail:
                os.makedirs("{}/{}".format(subdir, names[None]), exist_ok=True)
                                          
            for p, s in zip(proxies, results):
                prefix = names[0] if s == 0 else names[None]
                with open(os.path.join(subdir,"{}/{}".format(prefix, p.hostname)), "w") as stamp:
                    stamp.write("{}\n".format(s))

        # return 0 only if all hosts have returned 0
        # otherwise, return 1
        failures = [ r for r in results if r != 0 ]
        overall = 0 if len(failures) == 0 else 1
        return overall

if __name__ == '__main__':
    exit(Apssh().main())
