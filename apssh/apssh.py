#!/usr/bin/env python3

"""
The apssh binary makes a rather straightforward use of the library,
except maybe for the way it handles the fuzzy notion of targets,
that can be defined as either hostnames directly, or from files that contain
hostnames, or from directories that contain files named after hostnames.
"""

# allow catch-all exceptions
# pylint: disable=W0703

# for using a locally cloned branch of asyncssh
# import sys
# sys.path.insert(0, "../../asyncssh/")

import os
from pathlib import Path
import argparse

from asynciojobs import Scheduler

from .util import print_stderr
from .config import (default_time_name, default_timeout, default_username,
                     default_remote_workdir, local_config_dir)
from .sshproxy import SshProxy
from .formatters import (RawFormatter, ColonFormatter,
                         TimeColonFormatter, SubdirFormatter,
                         TerminalFormatter)
from .keys import load_private_keys
from .version import __version__ as apssh_version
from .sshjob import SshJob

from .commands import Run, RunScript, RunString


class Apssh:
    """
    Main class for apssh utility
    """

    def __init__(self):
        self.proxies = []
        self.formatter = None
        #
        self.parser = None
        self.parsed_args = None
        self.loaded_private_keys = None

    def __repr__(self):
        return "".join([str(p) for p in self.proxies])

    # returns a valid Path object, or None
    @staticmethod
    def locate_file(file):                              # pylint: disable=C0111
        path = Path(file)
        if path.exists():
            return path
        if not path.is_absolute():
            in_home = local_config_dir / path
            # somehow pylints figured in_home is a PurePath
            if in_home.exists():                        # pylint: disable=E1101
                return in_home
        return None

    def analyze_target(self, target):
        """
        This function is used to guess the meaning of all the targets passed
        to the ``apssh`` command through its ``-t/--target`` option.

        Parameters:
          target: a string passed to ``--target``

        Returns:
          (bool, list): a tuple, whose meaning is described below.

        A target can be specified as either

        * a **filename**. If it is a relative filename it is also searched
          in ``~/.apssh``. If an existing file can be located this way,
          and it can be parsed, then the returned object will be of the form::

              True, [ hostname1, ...]

        * a **directory name**. Here again the search is also done in
          ``~/.apssh``. If an existing directory can be found,
          all the simple files that are found immediately under the
          specified directory are taken as hostnames, and in this case
          ``analyze_target`` returns::

              True, [ hostname1, ...]

          This is notably for use together with the ``--mark`` option,
          so that one can easily select reachable nodes only,
          or just as easily exclude failing nodes.

        * otherwise, the incoming target is then expected to be a string that
          directly contains the hostnames, and so it is simply split along
          white spaces, and the return code is then::

              True, [ hostname1, ...]

        * If anything goes wrong, return code is::

              False, []

          for example, this is the case when the file exists
          but cannot be parsed - in which case it is probably not a hostname.

        """
        names = []
        # located is a Path object - or None
        located = self.locate_file(target)
        if located:
            if located.is_dir():
                # directory
                onlyfiles = [f for f in os.listdir(target)
                             if (located / f).is_file()]
                return True, onlyfiles
            else:
                # file
                try:
                    with located.open() as inputfile:
                        for line in inputfile:
                            line = line.strip()
                            if line.startswith('#'):
                                continue
                            line = line.split()
                            for token in line:
                                names += token.split()
                    return True, names
                except FileNotFoundError as exc:
                    return False, None
                except Exception as exc:
                    print_stderr(f"Unexpected exception when parsing file {target}, {exc}")
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
    def user_host(self, target):                        # pylint: disable=C0111
        try:
            user, hostname = target.split('@')
            return user, hostname
        except Exception:
            return self.parsed_args.login, target

    def create_proxies(self, gateway):                  # pylint: disable=C0111
        # start with parsing excludes if any
        excludes = set()
        for exclude in self.parsed_args.excludes:
            parsed, cli_excludes = self.analyze_target(exclude)
            excludes.update(cli_excludes)
        if self.parsed_args.dry_run:
            print(f"========== {len(excludes)} excludes found:")
            for exclude in excludes:
                print(exclude)

        # gather targets as mentioned in -t -x args
        hostnames = []
        actually_excluded = 0
        # read input file(s)
        for target in self.parsed_args.targets:
            parsed, cli_targets = self.analyze_target(target)
            if not parsed:
                print(f"WARNING: ignoring target {target}")
                continue
            for target2 in cli_targets:
                if target2 not in excludes:
                    hostnames.append(target2)
                else:
                    actually_excluded += 1
        if not hostnames:
            print("it makes no sense to run apssh without any hostname")
            self.parser.print_help()
            exit(1)

        if self.parsed_args.dry_run:
            print(f"========== {len(hostnames)} hostnames selected"
                  f"({actually_excluded} excluded):")
            for hostname in hostnames:
                print(hostname)
            exit(0)

        # create proxies
        self.proxies = [SshProxy(hostname, username=username,
                                 keys=self.loaded_private_keys,
                                 gateway=gateway,
                                 formatter=self.get_formatter(),
                                 timeout=self.parsed_args.timeout,
                                 debug=self.parsed_args.debug)
                        for username, hostname in (self.user_host(target)
                        for target in hostnames)]       # pylint: disable=c0330
        return self.proxies

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
            for now there no wildcard mechanism is supported here;
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
        self.loaded_private_keys = load_private_keys(
            self.parsed_args.keys, args.verbose or args.debug)
        if not self.loaded_private_keys and not args.ok_if_no_key:
            print("Could not find any usable key - exiting")
            exit(1)

        # initialize a gateway proxy if --gateway is specified
        gateway = None
        if args.gateway:
            gwuser, gwhost = self.user_host(args.gateway)
            gateway = SshProxy(hostname=gwhost, username=gwuser,
                               keys=self.loaded_private_keys,
                               formatter=self.get_formatter(),
                               timeout=self.parsed_args.timeout,
                               debug=self.parsed_args.debug)

        proxies = self.create_proxies(gateway)
        if args.verbose:
            print_stderr(f"apssh is working on {len(proxies)} nodes")

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
                    print("Warning: file not found '{}'\n"
                          "=> Using RunString instead".
                          format(script))
                command_class = RunString

        for proxy in proxies:
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
            for proxy, result in zip(proxies, results):
                print(f"PROXY {proxy.hostname} -> {result}")
        # marks
        names = {0: '0ok', None: '1failed'}
        if subdir and self.parsed_args.mark:
            # do we need to create the subdirs
            need_ok = [s for s in results if s == 0]
            if need_ok:
                os.makedirs(f"{subdir}/{names[0]}", exist_ok=True)
            need_fail = [s for s in results if s != 0]
            if need_fail:
                os.makedirs(f"{subdir}/{names[None]}", exist_ok=True)

            for proxy, result in zip(proxies, results):
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
