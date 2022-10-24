"""
This internal class is in charge of dealing with the scope of a apssh session
that can be defined as either hostnames directly, or from files that contain
hostnames, or from directories that contain files named after hostnames.
"""

from pathlib import Path

from .util import print_stderr
from .sshproxy import SshProxy
from .config import local_config_dir

class Targets:
    """
    from the main CLI options, and notably --target --gateway --exclude and --login,
    this class can build a collection of the SshProxy (SshNode actually)
    instances that are targetted
    """

    def __init__(self, target_strs, gateway_str, *, login, excludes,
                 private_keys, formatter,
                 timeout, debug, dry_run):
        self.target_strs = target_strs
        self.gateway_str = gateway_str
        self.login = login
        self.excludes = excludes
        self.private_keys = private_keys
        self.formatter = formatter
        self.timeout = timeout
        self.debug = debug
        self.dry_run = dry_run
        #
        self.proxies = []

        # initialize a gateway proxy if --gateway is specified
        self.gateway = None
        if gateway_str:
            gwuser, gwhost = self.user_host(gateway_str)
            self.gateway = SshProxy(
                hostname=gwhost, username=gwuser,
                keys=private_keys, formatter=formatter,
                timeout=timeout, debug=debug)

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
                onlyfiles = [str(f.name) for f in located.iterdir() if f.is_file()]
                return True, onlyfiles
            else:
                # file
                try:
                    with located.open() as inputfile: # pylint: disable=unspecified-encoding
                        for line in inputfile:
                            line = line.strip()
                            if line.startswith('#'):
                                continue
                            line = line.split()
                            for token in line:
                                names += token.split()
                    return True, names
                except FileNotFoundError:
                    return False, None
                except Exception as exc:                     # pylint: disable=broad-except
                    print_stderr(f"Unexpected exception when parsing file {target}, {exc}")
                    if self.debug:
                        import traceback          # pylint: disable=import-outside-toplevel
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
        except ValueError:
            return self.login, target


    def create_proxies(self):                  # pylint: disable=C0111
        # start with parsing excludes if any
        excludes = set()
        for exclude in self.excludes:
            parsed, cli_excludes = self.analyze_target(exclude)
            excludes.update(cli_excludes)
        if self.dry_run:
            print(f"========== {len(excludes)} excludes found:")
            for exclude in excludes:
                print(exclude)

        # gather targets as mentioned in -t -x args
        hostnames = []
        actually_excluded = 0
        # read input file(s)
        for target in self.target_strs:
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
            raise ValueError("empty targets")

        if self.dry_run:
            print(f"========== {len(hostnames)} hostnames selected"
                  f"({actually_excluded} excluded):")
            for hostname in hostnames:
                print(hostname)
            exit(0)

        # create proxies
        self.proxies = [SshProxy(hostname, username=username,
                                 keys=self.private_keys,
                                 gateway=self.gateway,
                                 formatter=self.formatter,
                                 timeout=self.timeout,
                                 debug=self.debug)
                        for username, hostname in (self.user_host(target)
                        for target in hostnames)]       # pylint: disable=c0330
        return self.proxies
