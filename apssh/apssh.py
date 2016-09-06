#!/usr/bin/env python3


# for using the develop branch of asyncssh
#import sys
#sys.path.insert(0, "../../asyncssh/")

import os, os.path
import time
import argparse
import asyncio

from .config import default_time_name, default_timeout, default_username, default_private_key, default_remote_workdir
from .sshproxy import SshProxy
from .formatters import RawFormatter, ColonFormatter, SubdirFormatter
from .window import gather_window
from .util import print_stderr

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
                        names += token.split()
            return True, names
        except FileNotFoundError as e:
            return False, None
        except Exception as e:
            print_stderr("Unexpected exception when parsing file {}, {}".format(filename, e))
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
                cli_excludes = exclude.split()
                excludes.add(cli_excludes)
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
                cli_targets = target.split()
                for target in cli_targets:
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
                run_name = default_time_name
                self.formatter = SubdirFormatter(run_name)
            elif self.parsed_args.out_dir:
                self.formatter = SubdirFormatter(self.parsed_args.out_dir)
            else:
                self.formatter = ColonFormatter()
        return self.formatter
    
    def main(self):
        self.parser = parser = argparse.ArgumentParser()
        # scope - on what hosts
        parser.add_argument("-t", "--target", dest='targets', action='append', default=[],
                            help="comma-separated list of targets (hostnames or filenames) - additive")
        parser.add_argument("-x", "--exclude", dest='excludes', action='append', default=[],
                            help="comma-separated list of excludes (hostnames or filenames) - additive")
        # global settings
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
                            available with the -d and -o options only.

                            When specified, then for all nodes there will be a stamp created
                            in the output subdir, named either 0ok/<hostname> for successful nodes,
                            or 1failed/<hostname> for the other ones.
                            The stamp will contain a single line with the returned code, or 'None'
                            if the node was not reachable at all""")
        parser.add_argument("-f", "--file", default=None,
                            help="""The name of a local script that will be run remotely.
                            It should be executable. On the remote boxes it will be installed and run in
                            the {} directory
                            """.format(default_remote_workdir))

        
        # turn on debugging
        parser.add_argument("-D", "--debug", action='store_true', default=False)

        # the commands to run
        parser.add_argument("commands", nargs=argparse.REMAINDER, type=str,
                            help="""
                            command to run remotely. If that command itself contains options,
                            it is a recommended good practice to
                            insert `--` before the actual command.  If
                            the -f option is provided, it replaces the
                            commands to be executed, so these should be omitted""")

        args = self.parsed_args = parser.parse_args()

        ### manual check for mutual exclusion of --file / positionals
        if not args.commands and not args.file:
            print("You must provide either a command or a file containing the script to be run")
            parser.print_help()
            exit(1)
        if args.commands and args.file:
            # XXX : probably we should allow this form to pass arguments to the script...
            print("You may provide a command to run **OR** a file containing a script, not both")
            parser.print_help()
            exit(1)
        
        proxies = self.create_proxies()

        if args.commands:
            command = " ".join(args.commands)
            tasks = [ proxy.connect_and_run(command) for proxy in proxies ]
        else:
            ### an executable is provided on the command line
            if not os.path.exists(args.file):
                print("File not found {}".format(args.file))
                parser.print_help()
                exit(1)
            # xxx could also check it's executable
            
            # in this case a first pass is required to push the code
            tasks = [ proxy.connect_put_and_run(args.file) for proxy in proxies ]


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

