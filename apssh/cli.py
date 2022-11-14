#!/usr/bin/env python3

"""
The apssh CLI command makes a rather straightforward use of the library,
except maybe for the way it handles the fuzzy notion of targets
which is the purpose of targets.py
"""

# allow catch-all exceptions
# pylint: disable=W0703

# for using a locally cloned branch of asyncssh
# import sys
# sys.path.insert(0, "../../asyncssh/")

import sys
from pathlib import Path
import argparse
import re

from asynciojobs import Scheduler

from .util import print_stderr
from .config import (default_time_name, default_timeout, default_remote_workdir)
from .formatters import (RawFormatter, ColonFormatter,
                         TimeColonFormatter, SubdirFormatter,
                         TerminalFormatter, shorten_hostname)
from .keys import load_private_keys
from .version import __version__ as apssh_version
from .sshjob import SshJob
from .commands import Run, RunScript, RunString, Push
from .targets import Targets


class CliWithFormatterOptions:         # pylint: disable=too-few-public-methods
    """
    the code that deals with formatter-related options
    """
    def __init__(self):
        self.formatter = None

    def add_formatter_options(self, parser): # pylint: disable=missing-function-docstring
        parser.add_argument(
            "-r", "--raw-format", default=False, action='store_true',
            help="""
            produce raw result, incoming lines are shown as-is without hostname
            """)
        parser.add_argument(
            "-tc", "--time-colon-format", default=False, action='store_true',
            help="equivalent to --format '{time}:{host}:{linenl}")
        parser.add_argument(
            "-f", "--format", default=None, action='store',
            help="""specify output format, which may include
* `strftime` formats like e.g. %%H-%%M, and one of the following:
* {user} for the remote username,
* {fqdn} for the target hostname,
* {host} for the target hostname with its domain stripped,
* {linenl} for the actual line output (which contains the actual newline)
* {line} for the actual line output (without the newline)
* {nl} for adding a newline
* {time} is a shorthand for %%H-%%M-%%S""")
        parser.add_argument(
            "-o", "--out-dir", default=None,
            help="specify directory where to store results")
        parser.add_argument(
            "-d", "--date-time", default=None, action='store_true',
            help="use date-based directory to store results")

    def _get_formatter(self, parsed_args):
        if self.formatter is None:
            verbose = parsed_args.verbose
            if parsed_args.format:
                self.formatter = TerminalFormatter(
                    parsed_args.format, verbose=verbose)
            elif parsed_args.raw_format:
                self.formatter = RawFormatter(verbose=verbose)
            elif parsed_args.time_colon_format:
                self.formatter = TimeColonFormatter(verbose=verbose)
            elif parsed_args.date_time:
                run_name = default_time_name
                self.formatter = SubdirFormatter(run_name, verbose=verbose)
            elif parsed_args.out_dir:
                self.formatter = SubdirFormatter(parsed_args.out_dir,
                                                 verbose=verbose)
            else:
                self.formatter = ColonFormatter(verbose=verbose)
        return self.formatter


class Apssh(CliWithFormatterOptions):
    """
    Main class for apssh utility
    """

    def __init__(self):
        self.formatter = None
        #
        self.proxies = None
        super().__init__()

    def __repr__(self):
        return "".join(str(p) for p in self.proxies)

    def main(self, *test_argv):       # pylint: disable=r0915,r0912,r0914,c0111
        parser = argparse.ArgumentParser()
        targets = Targets()
        targets.add_target_options(parser)
        parser.add_argument("-L", "--list-targets", default=False, action='store_true',
                            help="just lists the targets and exits")
        # global settings
        parser.add_argument(
            "-w", "--window", type=int, default=0,
            help="""
            specify how many connections can run simultaneously;
            default is no limit
            """)
        # ssh settings
        parser.add_argument(
            "-c", "--connect-timeout", dest='timeout',
            type=float, default=default_timeout,
            help=f"specify connection timeout, default is {default_timeout}s")
        parser.add_argument(
            "-k", "--key", dest='keys',
            default=None, action='append', type=str,
            help="""
            The default is for apssh to locate an ssh-agent
            through the SSH_AUTH_SOCK environment variable.
            If this cannot be found, or has an empty set of keys,
            then the user should specify private key file(s) - additive
            """)
        parser.add_argument(
            "-K", "--ok-if-no-key", default=False, action='store_true',
            help="""
            When no key can be found, apssh won't even bother
            to try and connect. With this option it proceeds
            even with no key available.
            """
            )
        # how to store results - choice of formatter
        self.add_formatter_options(parser)
        # the mark option - not quite sure if that's going to stick
        parser.add_argument(
            "-m", "--mark", default=False, action='store_true',
            help="""
            available with the -d and -o options only.

            When specified, then for all nodes there will be a file created
            in the output subdir, named either
            0ok/<hostname> for successful nodes,
            or 1failed/<hostname> for the other ones.

            This mark file will contain a single line with the returned code,
            or 'None' if the node was not reachable at all
            """)

        # usual stuff
        parser.add_argument(
            "-n", "--dry-run", default=False, action='store_true',
            help="Only show details on selected hostnames")
        parser.add_argument(
            "-v", "--verbose",
            action='store_true', default=False)
        parser.add_argument(
            "-D", "--debug", action='store_true', default=False)
        parser.add_argument(
            "-V", "--version",
            action='store_true', default=False)

        # script mode
        parser.add_argument(
            "-s", "--script", action='store_true', default=False,
            help=f"""If this flag is present, the first element of the remote
            command is assumed to be either the name of a local script, or,
            if this is not found, the body of a local script, that will be
            copied over before being executed remotely.
            In this case it should be executable.

            On the remote boxes it will be installed
            and run in the {default_remote_workdir} directory.
            """)
        parser.add_argument(
            "-i", "--includes", dest='includes', default=[], action='append',
            help="""for script mode only : a list of local files that are
            pushed remotely together with the local script,
            and in the same location; useful when you want to
            to run remotely a shell script that sources other files;
            remember that on the remote end all files (scripts and includes)
            end up in the same location""")
        # the commands to run
        parser.add_argument(
            "commands", nargs=argparse.REMAINDER, type=str,
            help="""
            command to run remotely.

            If the -s or --script option is provided, the first argument
            here should denote a (typically script) file **that must exist**
            on the local filesystem. This script is then copied over
            to the remote system and serves as the command for remote execution
            """)

        if test_argv:
            args = parser.parse_args(test_argv)
        else:
            args = parser.parse_args()

        # helpers
        if args.version:
            print(f"apssh version {apssh_version}")
            sys.exit(0)

        # manual check for REMAINDER
        if not args.commands:
            print("You must provide a command to be run remotely")
            parser.print_help()
            sys.exit(1)

        # load keys
        private_keys = load_private_keys(args.keys, args.verbose or args.debug)
        if not private_keys and not args.ok_if_no_key:
            print("Could not find any usable key - exiting")
            sys.exit(1)

        targets.init_from_args(args, private_keys, self._get_formatter(args))

        try:
            self.proxies = targets.create_proxies()
            if args.debug:
                for proxy in self.proxies:
                    print(f"using target {proxy}")
        except ValueError:
            print("it makes no sense to run apssh without any target")
            parser.print_help()
            sys.exit(1)

        if args.list_targets:
            for proxy in self.proxies:
                print(proxy)
            sys.exit(0)

        if args.verbose:
            print_stderr(f"apssh is working on {len(self.proxies)} nodes")

        window = args.window

        # populate scheduler
        scheduler = Scheduler(verbose=args.verbose)
        if not args.script:
            command_class = Run
            extra_kwds_args = {}
        else:
            # try RunScript
            command_class = RunScript
            extra_kwds_args = {'includes': args.includes}
            # but if the filename is not found then use RunString
            script = args.commands[0]
            if not Path(script).exists():
                if args.verbose:
                    print(f"Warning: file not found '{script}'\n"
                          f"=> Using RunString instead")
                command_class = RunString

        for proxy in self.proxies:
            scheduler.add(
                SshJob(node=proxy,
                       critical=False,
                       command=command_class(*args.commands,
                                             **extra_kwds_args)))

        # pylint: disable=w0106
        scheduler.jobs_window = window
        if not scheduler.run():
            scheduler.debrief()
        retcods = [job.result() for job in scheduler.jobs]

        ##########
        # print on stdout the name of the output directory
        # useful mostly with -d :
        subdir = self._get_formatter(args).run_name \
            if isinstance(self._get_formatter(args), SubdirFormatter) \
            else None
        if subdir:
            print(subdir)

        # marks
        names = {0: '0ok', None: '1failed'}
        if subdir and args.mark:
            # do we need to create the subdirs
            if any(retcod==0 for retcod in retcods):
                (Path(subdir) / names[0]).mkdir(exist_ok=True)
            if any(retcod!=0 for retcod in retcods):
                (Path(subdir) / names[None]).mkdir(exist_ok=True)

            for proxy, result in zip(self.proxies, retcods):
                prefix = names[0] if result == 0 else names[None]
                mark_path = Path(subdir) / prefix / proxy.hostname
                with mark_path.open("w") as mark:
                    mark.write(f"{result}\n")

        # details on the individual retcods - a bit hacky
        for proxy, result in zip(self.proxies, retcods):
            if result is None:
                print_stderr(f"{proxy.hostname}: apssh WARNING - no result !")
            elif args.debug:
                print(f"DEBUG: PROXY {proxy.hostname} -> {result}")


        # when in gateway mode, the gateway proxy # pylint: disable=fixme
        # never gets disconnected, which probably is just fine

        # return 0 only if all hosts have returned 0
        # otherwise, return 1
        return 0 if all(retcod == 0 for retcod in retcods) else 1


class Copy:
    """
    the common ancestor for Appush and Appull
    """

    @staticmethod
    def is_remote(location):
        """
        check if location contains a @: magic string and if so,
        returns the remote location
        """
        if location.startswith("@:"):
            return location[2:]
        else:
            return None

    @staticmethod
    def instantiate(template, proxy):
        fqdn = proxy.hostname
        host = shorten_hostname(proxy.hostname)
        user = proxy.username
        return (template
                   .replace("{fqdn}", fqdn or "")
                   .replace("{host}", host or "")
                   .replace("{user}", f"{user}@" if user else ""))


class Appush(CliWithFormatterOptions, Copy):

    def __init__(self):
        self.formatter = None
        #
        self.proxies =  None

    def main(self):
        parser = argparse.ArgumentParser()
        targets = Targets()
        targets.add_target_options(parser)
        # global settings
        parser.add_argument(
            "-w", "--window", type=int, default=0,
            help="""
            specify how many connections can run simultaneously;
            default is no limit
            """)
        # ssh settings
        parser.add_argument(
            "-c", "--connect-timeout", dest='timeout',
            type=float, default=default_timeout,
            help=f"specify connection timeout, default is {default_timeout}s")
        parser.add_argument(
            "-k", "--key", dest='keys',
            default=None, action='append', type=str,
            help="""
            The default is for apssh to locate an ssh-agent
            through the SSH_AUTH_SOCK environment variable.
            If this cannot be found, or has an empty set of keys,
            then the user should specify private key file(s) - additive
            """)
        # how to store results - choice of formatter
        self.add_formatter_options(parser)

        # usual stuff
        parser.add_argument(
            "-n", "--dry-run", default=False, action='store_true',
            help="Only show details on selected hostnames")
        parser.add_argument(
            "-v", "--verbose",
            action='store_true', default=False)
        parser.add_argument(
            "-D", "--debug", action='store_true', default=False)
        ### xxx todo add other relevant options


        parser.add_argument(
            "local_files", nargs='+',
            help="the local file(s) to transfer")
        parser.add_argument(
            "remote_location", nargs=1,
            help="where to transfer them on the remote targets;"
                 " must be of the form @:remote-location;"
                 " if several local files are provided,"
                 " should be an existing directory"
        )


        args = parser.parse_args()

        # if args.version:
        #     print(f"apssh version {apssh_version}")
        #     sys.exit(0)

        # check files
        if not (remote := self.is_remote(args.remote_location[0])):
            print(f"{args.remote_location} is not remote - should start with @:")
            parser.print_help()
            sys.exit(1)

        local_files = args.local_files

        private_keys = load_private_keys(args.keys, args.verbose)
        if not private_keys and not args.ok_if_no_key:
            print("Could not find any usable key - exiting")
            sys.exit(1)

        targets.init_from_args(args, private_keys, self._get_formatter(args))
        try:
            self.proxies = targets.create_proxies()
            if args.debug:
                for proxy in self.proxies:
                    print(f"using target {proxy}")
        except ValueError:
            print("it makes no sense to run apssh without any target")
            parser.print_help()
            sys.exit(1)

        window = args.window

        # populate scheduler
        scheduler = Scheduler(verbose=args.verbose)
        for proxy in self.proxies:
            scheduler.add(
                SshJob(
                    node=proxy,
                    critical=False,
                    command=Push(
                        [self.instantiate(local, proxy)
                            for local in local_files],
                        self.instantiate(remote, proxy),
                        verbose=args.verbose or args.debug)))

        # pylint: disable=w0106
        scheduler.jobs_window = window
        if not scheduler.run():
            scheduler.debrief()
        retcods = [job.result() for job in scheduler.jobs]

        # return 0 only if all hosts have returned 0
        # otherwise, return 1
        return 0 if all(retcod == 0 for retcod in retcods) else 1
