#!/usr/bin/env python3


# for using the develop branch of asyncssh
#import sys
#sys.path.insert(0, "../../asyncssh/")

import os, os.path
import time
import argparse
import asyncio

from .util import print_stderr
from .config import default_time_name, default_timeout, default_username, default_private_keys, default_remote_workdir, local_config_dir
from .sshproxy import SshProxy
from .formatters import RawFormatter, ColonFormatter, TimeColonFormatter, SubdirFormatter
from .window import gather_window
from .keys import import_private_key, load_agent_keys
from .version import version as apssh_version

class Apssh:
    """
    Main class for apssh utility
    """

    def __init__(self):
        self.proxies = []
        self.formatter = None

    def __repr__(self):
        return "".join([str(p) for p in self.proxies])

    def locate_file(self, file):
        if os.path.exists(file):
            return file
        if not os.path.isabs(file):
            in_home = os.path.join(local_config_dir, file)
            if os.path.exists(in_home):
                return in_home

    def analyze_target(self, target):
        """
        A target can be specified as either
        * a filename
          Searched also in ~/.apssh
          If the provided filename exists and could be parsed, returned object will be
            True, [ hostname1, ...]
        * a directory name
          This is for use together with the --mark option, so that one can easily select reachable nodes only, 
          or just as easily exclude failing nodes
          all the simple files that are found immediately under the specified directory are taken as hostnames
          XXX it would make sense to check there is at least one dot in their name, but I'm not sure about that yet
          Here again if things work out we return
            True, [ hostname1, ...]
        * otherwise
          the target is then expected a string passed to -t on the command line,
          so it is simply split according to white spaces before being returned as
            True, [ hostname1, ...]
        * If anything goes wrong, return code is 
            False, []
          e.g. the file exists but cannot be parsed
          not sure this truly is useful
        """
        names = []
        located = self.locate_file(target)
        if located:
            if os.path.isdir(located):
    # directory
                onlyfiles = [ f for f in os.listdir(target)
                              if os.path.isfile(os.path.join(located, f))]
                return True, onlyfiles
            else:
    # file
                try:
                    with open(located) as input:
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
                    print_stderr("Unexpected exception when parsing file {}, {}".format(target, e))
                    if self.parsed_args.debug:
                        import traceback
                        traceback.print_exc()
                    return False, None
        else:
    # string
            return True, target.split()

    # create tuples username, hostname
    # use the username if already present in the target,
    # otherwise the one specified with --username
    def user_host(self, target):
        try:
            user, hostname = target.split('@')
            return user, hostname
        except:
            return self.parsed_args.username, target

    def create_proxies(self, gateway):
        # start with parsing excludes if any
        excludes = set()
        for exclude in self.parsed_args.excludes:
            parsed, cli_excludes = self.analyze_target(exclude)
            excludes.update(cli_excludes)
        if self.parsed_args.dry_run:
            print("========== {} excludes found:".format(len(excludes)))
            for exclude in excludes:
                  print(exclude)

        # gather targets as mentioned in -t -x args
        hostnames = []
        actually_excluded = 0
        # read input file(s)
        for target in self.parsed_args.targets:
            parsed, cli_targets = self.analyze_target(target)
            for target in cli_targets:
                if target not in excludes:
                    hostnames.append(target)
                else:
                    actually_excluded += 1
        if not hostnames:
            self.parser.print_help()
            exit(1)

        if self.parsed_args.dry_run:
            print("========== {} hostnames selected ({} excluded):"
                  .format(len(hostnames), actually_excluded))
            for hostname in hostnames:
                print(hostname)
            exit(0)

        # create proxies
        self.proxies = [ SshProxy(hostname, username=username,
                                  keys = self.loaded_private_keys,
                                  gateway = gateway,
                                  formatter = self.get_formatter(),
                                  timeout = self.parsed_args.timeout,
                                  debug = self.parsed_args.debug)
                         for username, hostname in  (self.user_host(target) for target in hostnames) ]
        return self.proxies

    def get_formatter(self):
        if self.formatter is None:
            verbose = self.parsed_args.verbose
            if self.parsed_args.raw_format:
                self.formatter = RawFormatter(verbose = verbose)
            elif self.parsed_args.time_colon_format:
                self.formatter = TimeColonFormatter(verbose = verbose)
            elif self.parsed_args.date_time:
                run_name = default_time_name
                self.formatter = SubdirFormatter(run_name, verbose = verbose)
            elif self.parsed_args.out_dir:
                self.formatter = SubdirFormatter(self.parsed_args.out_dir,
                                                 verbose = verbose)
            else:
                self.formatter = ColonFormatter(verbose = verbose)
        return self.formatter
    
    def load_private_keys(self):
        """
        Here's how `apssh` locates private keys:

        ### If no keys are specified using the `-k` command line option 

        * (A) if an *ssh agent* can be reached using the `SSH_AUTH_SOCK` environment variable,
          and offers a non-empty list of keys, `apssh` will use the keys loaded in the agent
          (**NOTE:** use `ssh-add` for managing the keys known to the agent)
        * (B) otherwise, `apssh` will use `~/.ssh/id_rsa` and `~/.ssh/id_dsa` if existent

        ### If keys are specified on the command line

        * (C) That exact list is used for loading private keys
        """
        filenames = []
        if self.parsed_args.private_keys is None:
            keys = load_agent_keys()
            # agent has stuff : let's use it
            if keys:
                self.loaded_private_keys = keys
                return
            filenames = default_private_keys
        else:
            filenames = self.parsed_args.private_keys
        keys = [ import_private_key(filename) for filename in filenames ]
        self.loaded_private_keys = [ k for k in keys if k ]

    def main(self):
        self.parser = parser = argparse.ArgumentParser()
        # scope - on what hosts
        parser.add_argument("-s", "--script", action='store_true', default=False,
                            help="""If this flag is present, the first element of the remote command 
                            is assumed to be the name of a local script, that will be copied over
                            before being executed remotely.
                            In this case it should be executable.
                            On the remote boxes it will be installed and run in the {} directory.
                            """.format(default_remote_workdir))
        parser.add_argument("-i", "--includes", dest='includes', default=[], action='append',
                            help="""for script mode only : a list of local files that are pushed remotely 
                            together with the local script, and in the same location; useful when you want to
                            to run remotely a shell script that sources other files; remember that on the remote
                            end all files (scripts and includes) end up in the same location""")
        parser.add_argument("-t", "--target", dest='targets', action='append', default=[],
                            help="""
                            specify targets (additive); each target can be either 
                              * a space-separated list of hostnames
                              * the name of a file containing hostnames
                              * the name of a directory containing files named after hostnames; 
                                see e.g. the --mark option
                            """)
        parser.add_argument("-x", "--exclude", dest='excludes', action='append', default=[],
                            help="""
                            like --target, but for specifying exclusions; 
                            for now there no wildcard mechanism is supported here;
                            also the order in which --target and --exclude options are mentioned does not matter;
                            use --dry-run to only check for the list of applicable hosts
                            """)
        # global settings
        parser.add_argument("-w", "--window", type=int, default=0,
                            help="specify how many connections can run simultaneously; default is no limit")
        parser.add_argument("-c", "--connect-timeout", dest='timeout',
                            type=float, default=default_timeout,
                            help="specify connection timeout, default is {}s".format(default_timeout))
        # ssh settings
        parser.add_argument("-u", "--username", default=default_username,
                            help="remote user name - default is {}".format(default_username))
        parser.add_argument("-k", "--key",
                            default=None, action='append', type=str,
                            help="""
                            The default is for apssh to locate an ssh-agent through the SSH_AUTH_SOCK
                            environment variable. If this cannot be found, or has an empty set of keys,
                            then the user should specify private key file(s) - additive""")
        parser.add_argument("-g", "--gateway", default=None,
                            help="specify a gateway for 2-hops ssh - either hostname or username@hostname")
        ##### how to store results
        # terminal
        parser.add_argument("-r", "--raw-format", default=False, action='store_true',
                            help="produce raw result")
        parser.add_argument("-tc", "--time-colon-format", default=False, action='store_true',
                            help="produce output with format time:hostname:line")

        # filesystem
        parser.add_argument("-o", "--out-dir", default=None,
                            help="specify directory where to store results")
        parser.add_argument("-d", "--date-time", default=None, action='store_true',
                            help="use date-based directory to store results")
        parser.add_argument("-m", "--mark", default=False, action='store_true',
                            help="""
                            available with the -d and -o options only.

                            When specified, then for all nodes there will be a file created
                            in the output subdir, named either 0ok/<hostname> for successful nodes,
                            or 1failed/<hostname> for the other ones.
                            This mark file will contain a single line with the returned code, or 'None'
                            if the node was not reachable at all""")

        
        # usual stuff
        parser.add_argument("-n", "--dry-run", default=False, action='store_true',
                            help="Only show details on selected hostnames")
        parser.add_argument("-v", "--verbose", action='store_true', default=False)
        parser.add_argument("-D", "--debug", action='store_true', default=False)
        parser.add_argument("-V", "--version", action='store_true', default=False)

        # the commands to run
        parser.add_argument("commands", nargs=argparse.REMAINDER, type=str,
                            help="""
                            command to run remotely. 

                            If the -s or --script option is provided, the first argument
                            here should denote a (typically script) file **that must exist**
                            on the local filesystem. This script is then copied over
                            to the remote system and serves as the command for remote execution""")

        args = self.parsed_args = parser.parse_args()

        ### helpers
        if args.version:
            print("apssh version {}".format(apssh_version))
            exit(1)

        ### manual check for REMAINDER
        if not args.commands:
            print("You must provide a command to be run remotely")
            parser.print_help()
            exit(1)

        ### load keys
        self.load_private_keys()
        if self.parsed_args.debug:
            print("We have found {} keys".format(len(self.loaded_private_keys)))
            for key in self.loaded_private_keys:
                print(key)
        if not self.loaded_private_keys:
            print("Could not find any usable key - exiting")
            exit(1)

        ### initialize a gateway proxy if --gateway is specified
        gateway = None
        if args.gateway:
            gwuser, gwhost = self.user_host(args.gateway)
            gateway = SshProxy(hostname = gwhost, username = gwuser,
                               keys = self.loaded_private_keys,
                               formatter = self.get_formatter(),
                               timeout = self.parsed_args.timeout,
                               debug = self.parsed_args.debug)

        proxies = self.create_proxies(gateway)

        if not args.script:
            command = " ".join(args.commands)
            tasks = [ proxy.connect_run(command) for proxy in proxies ]
        else:
            ### an executable is provided on the command line
            script, r_args = args.commands[0], args.commands[1:]
            if not os.path.exists(script):
                print("File not found {}".format(script))
                parser.print_help()
                exit(1)
            # xxx could also check it's executable
            
            # in this case a first pass is required to push the code
            tasks = [ proxy.connect_put_run(script, includes=args.includes, *r_args) for proxy in proxies ]


        loop = asyncio.get_event_loop()
        window = self.parsed_args.window
        if not window:
            if self.parsed_args.debug:
                print("No window limit")
            results = loop.run_until_complete(asyncio.gather(*tasks,
                                                             return_exceptions = True))
        else:
            if self.parsed_args.debug:
                print("Window limit={}".format(window))
            results = loop.run_until_complete(gather_window(*tasks, window=window,
                                                            debug=args.debug,
                                                            return_exceptions = True))

        ### print on stdout the name of the output directory
        # useful mostly with -d : 
        subdir = self.get_formatter().run_name \
                 if isinstance(self.get_formatter(), SubdirFormatter) \
                    else None
        if subdir:
            print(subdir)
        ### details on the individual retcods - a bit rough
        if self.parsed_args.debug:
            for p, s in zip(proxies, results):
                print("PROXY {} -> {}".format(p.hostname, s))
        # marks
        names = { 0 : '0ok', None : '1failed'}
        if subdir and self.parsed_args.mark:
            # do we need to create the subdirs
            need_ok = [s for s in results if s==0]
            if need_ok:
                os.makedirs("{}/{}".format(subdir, names[0]), exist_ok=True)
            need_fail = [s for s in results if s!=0]
            if need_fail:
                os.makedirs("{}/{}".format(subdir, names[None]), exist_ok=True)
                                          
            for p, s in zip(proxies, results):
                prefix = names[0] if s == 0 else names[None]
                with open(os.path.join(subdir,"{}/{}".format(prefix, p.hostname)), "w") as mark:
                    mark.write("{}\n".format(s))

        # xxx - when in gateway mode, the gateway proxy never gets disconnected
        # which probably is just fine
        
        # return 0 only if all hosts have returned 0
        # otherwise, return 1
        failures = [ r for r in results if r != 0 ]
        overall = 0 if len(failures) == 0 else 1
        return overall

