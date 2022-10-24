#!/usr/bin/env python3

"""
The apssh binary makes a rather straightforward use of the library,
except maybe for the way it handles the fuzzy notion of targets
which is the puspose of targets.py
"""

# allow catch-all exceptions
# pylint: disable=W0703

# for using a locally cloned branch of asyncssh
# import sys
# sys.path.insert(0, "../../asyncssh/")

from pathlib import Path
import argparse

from asynciojobs import Scheduler

from .util import print_stderr
from .config import (default_time_name, default_timeout, default_username,
                     default_remote_workdir)
from .formatters import (RawFormatter, ColonFormatter,
                         TimeColonFormatter, SubdirFormatter,
                         TerminalFormatter)
from .keys import load_private_keys
from .version import __version__ as apssh_version
from .sshjob import SshJob
from .commands import Run, RunScript, RunString
from .targets import Targets

class Apssh:
    """
    Main class for apssh utility
    """

    def __init__(self):
        self.formatter = None
        #
        self.proxies = None
        self.parser = None
        self.parsed_args = None
        self.loaded_private_keys = None

    def __repr__(self):
        return "".join(str(p) for p in self.proxies)

    def get_formatter(self):                            # pylint: disable=C0111
        if self.formatter is None:
            verbose = self.parsed_args.verbose
            if self.parsed_args.format:
                self.formatter = TerminalFormatter(
                    self.parsed_args.format, verbose=verbose)
            elif self.parsed_args.raw_format:
                self.formatter = RawFormatter(verbose=verbose)
            elif self.parsed_args.time_colon_format:
                self.formatter = TimeColonFormatter(verbose=verbose)
            elif self.parsed_args.date_time:
                run_name = default_time_name
                self.formatter = SubdirFormatter(run_name, verbose=verbose)
            elif self.parsed_args.out_dir:
                self.formatter = SubdirFormatter(self.parsed_args.out_dir,
                                                 verbose=verbose)
            else:
                self.formatter = ColonFormatter(verbose=verbose)
        return self.formatter

    def main(self, *test_argv):  # pylint: disable=r0915,r0912,r0914,c0111
        self.parser = parser = argparse.ArgumentParser()
        # scope - on what hosts
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
        parser.add_argument(
            "-t", "--target", dest='targets', action='append', default=[],
            help="""
            specify targets (additive); at least one is required;
            each target can be either
            * a space-separated list of hostnames
            * the name of a file containing hostnames
            * the name of a directory containing files named after hostnames;
            see e.g. the --mark option
            """)
        parser.add_argument(
            "-x", "--exclude", dest='excludes', action='append', default=[],
            help="""
            like --target, but for specifying exclusions;
            for now no wildcard mechanism is supported here;
            also the order in which --target and --exclude options
            are mentioned does not matter;
            use --dry-run to only check for the list of applicable hosts
            """)
        # global settings
        parser.add_argument(
            "-w", "--window", type=int, default=0,
            help="""
            specify how many connections can run simultaneously;
            default is no limit
            """)
        parser.add_argument(
            "-c", "--connect-timeout", dest='timeout',
            type=float, default=default_timeout,
            help=f"specify connection timeout, default is {default_timeout}s")
        # ssh settings
        parser.add_argument(
            "-l", "--login", default=default_username,
            help=f"remote user name - default is {default_username}")
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
        parser.add_argument(
            "-g", "--gateway", default=None,
            help="""
            specify a gateway for 2-hops ssh
            - either hostname or username@hostname
            """)
        # how to store results
        # terminal
        parser.add_argument(
            "-r", "--raw-format", default=False, action='store_true',
            help="""
            produce raw result, incoming lines are shown as-is without hostname
            """)
        parser.add_argument(
            "-tc", "--time-colon-format", default=False, action='store_true',
            help="equivalent to --format '@time@:@host@:@line@")
        parser.add_argument(
            "-f", "--format", default=None, action='store',
            help="""specify output format, which may include
* `strftime` formats like e.g. %%H-%%M, and one of the following:
* @user@ for the remote username,
* @host@ for the target hostname,
* @line@ for the actual line output (which contains the actual newline)
* @time@ is a shorthand for %%H-%%M-%%S""")

        # filesystem
        parser.add_argument(
            "-o", "--out-dir", default=None,
            help="specify directory where to store results")
        parser.add_argument(
            "-d", "--date-time", default=None, action='store_true',
            help="use date-based directory to store results")
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
            args = self.parsed_args = parser.parse_args(test_argv)
        else:
            args = self.parsed_args = parser.parse_args()

        # helpers
        if args.version:
            print(f"apssh version {apssh_version}")
            exit(0)

        # manual check for REMAINDER
        if not args.commands:
            print("You must provide a command to be run remotely")
            parser.print_help()
            exit(1)

        # load keys
        private_keys = load_private_keys(
            self.parsed_args.keys, args.verbose or args.debug)
        if not private_keys and not args.ok_if_no_key:
            print("Could not find any usable key - exiting")
            exit(1)

        try:
            self.proxies = (Targets(
                args.targets, args.gateway,
                login=args.login, excludes=args.excludes,
                private_keys=private_keys, formatter=self.get_formatter(),
                timeout=args.timeout, debug=args.debug, dry_run=args.dry_run)
            .create_proxies())
            if args.debug:
                for proxy in self.proxies:
                    print(f"using target {proxy}")
        except ValueError:
            print("it makes no sense to run apssh without any target")
            self.parser.print_help()
            exit(1)

        if args.verbose:
            print_stderr(f"apssh is working on {len(self.proxies)} nodes")

        window = self.parsed_args.window

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
        results = [job.result() for job in scheduler.jobs]

        ##########
        # print on stdout the name of the output directory
        # useful mostly with -d :
        subdir = self.get_formatter().run_name \
            if isinstance(self.get_formatter(), SubdirFormatter) \
            else None
        if subdir:
            print(subdir)

        # details on the individual retcods - a bit hacky
        if self.parsed_args.debug:
            for proxy, result in zip(self.proxies, results):
                print(f"PROXY {proxy.hostname} -> {result}")
        # marks
        names = {0: '0ok', None: '1failed'}
        if subdir and self.parsed_args.mark:
            # do we need to create the subdirs
            need_ok = [s for s in results if s == 0]
            if need_ok:
                (Path(subdir) / names[0]).mkdir(exist_ok=True)
            need_fail = [s for s in results if s != 0]
            if need_fail:
                (Path(subdir) / names[None]).mkdir(exist_ok=True)

            for proxy, result in zip(self.proxies, results):
                prefix = names[0] if result == 0 else names[None]
                mark_path = Path(subdir) / prefix / proxy.hostname
                with mark_path.open("w") as mark:
                    mark.write(f"{result}\n")

        # xxx - when in gateway mode, the gateway proxy never gets disconnected
        # which probably is just fine

        # return 0 only if all hosts have returned 0
        # otherwise, return 1
        failures = [r for r in results if r != 0]
        overall = 0 if not failures else 1
        return overall
