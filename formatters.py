import os, os.path
import asyncio

# asyncio.TimeoutError() has a meaningful repr() but an empty str()
def ensure_visible(exc):
    if isinstance(exc, asyncio.TimeoutError):
        exc = repr(exc)
    return exc


class Formatter:
    """
    This class is an abstract class that allows to define
    how to handle the incoming line of a remote command
    
    This object is expected to be created manually outside of SshProxy logic,
    and then passed to SshProxy

    Examples:
    . RawFormatter:    just ouputs line on stdout
    . ColonFormatter:  outputs hostname + ':' + line - a la grep
    . SubdirFormatter: stores in <subdir>/<hostname> all outputs from that host
    """

    # this seems like a reasonable default
    def connection_failed(self, hostname, username, port, exc):
        exc = ensure_visible(exc)
        print("{}@{}:{} - Connection failed {}".format(hostname, username, port, exc))

    def session_failed(self, hostname, command, exc):
        exc = ensure_visible(exc)
        print("{} - Session failed {}".format(hostname, e))

    # events
    def connection_start(self, hostname):
        pass

    def connection_stop(self, hostname):
        pass    

    def session_start(self, hostname, command):
        pass

    def session_stop(self, hostname):
        pass    
    
    # the bulk of the matter
    def line(self, hostname, line):
        print("WARNING: class Formatter is intended as a pure abstract class")
        print("Received line {} from hostname {}".format(line, hostname))
        print("WARNING: class Formatter is intended as a pure abstract class")

        
class RawFormatter(Formatter):
    """
    Display raw lines as they come
    mostly useless, but useful for development
    """
    def __init__(self, debug):
        self.debug = debug
    def connection_start(self, hostname):
        if self.debug: print("RF CA: Connected to {}".format(hostname))
    def connection_stop(self, hostname):
        if self.debug: print("RF CO: Disconnected from {}".format(hostname))
    def session_start(self, hostname, command):
        if self.debug: print("RF SA: Session on {} started for command {}".format(hostname, command))
    def session_stop(self, hostname):
        if self.debug: print("RF SO: Session ended on {}".format(hostname))
    def line(self, hostname, line):
        print(line, end="")

class ColonFormatter(Formatter):
    """
    Display each line prepended with the hostname and a ':'
    """
    def line(self, hostname, line):
        print("{}:{}".format(hostname, line), end="")

class SubdirFormatter(Formatter):

    def __init__(self, run_name):
        self.run_name = run_name
        self._dir_checked = False

    def out(self, hostname):
        return os.path.join(self.run_name, hostname)

    def check_dir(self):
        # create directory if needed
        if not self._dir_checked:
            if not os.path.isdir(self.run_name):
                os.makedirs(self.run_name)
            self._dir_checked = True

    def connection_start(self, hostname):
        try:
            self.check_dir()
            # create output file
            with open(self.out(hostname), 'w') as out:
                pass
        except OSError as e:
            print("File permission problem {}".format(e))
            exit(1)
        except Exception as e:
            print("Unexpected error {}".format(e))
            exit(1)

    def line(self, hostname, line):
        with open(self.out(hostname), 'a') as out:
            out.write(line)
