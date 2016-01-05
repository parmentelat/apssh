import os, os.path

class Formatter:
    """
    This class is an abstract class that allows to define
    how to handle the incoming line of a remote command
    
    Protocol is quite simple
    * object is passed to SshProxy
    * method connection_start(hostname)       - defaults to noop - can do whatever initialization
    * method connection_stop(hostname)        - defaults to noop - can do whatever housecleaning
    * method session_start(hostname, command) - defaults to noop - can do whatever initialization
    * method session_stop(hostname)           - defaults to noop - can do whatever housecleaning
    * method line(hostname, line)             - is called each time a command issues a line

    Examples:
    . RawFormatter:    just ouputs line on stdout
    . ColonFormatter:  outputs hostname + ':' + line - a la grep
    . SubdirFormatter: creates file run/hostname with all outputs from that host
    """

    def __init__(self):
        pass

    def connection_start(self, hostname):
        pass

    # WARNING: as of the first rough implementation
    # this is never called
    def connection_stop(self, hostname):
        pass    

    def session_start(self, hostname, command):
        pass

    def session_stop(self, hostname):
        pass    
    
    def line(self, hostname, line):
        print("WARNING: class Formatter is intended as a pure abstract class")
        print("Received line {} from hostname {}".format(line, hostname))
        print("WARNING: class Formatter is intended as a pure abstract class")

        
class RawFormatter(Formatter):
    """
    Display raw lines as they come
    mostly useless, but useful for development
    """
    def connection_start(self, hostname):
        print("RF: Connected to {}".format(hostname))
    def connection_stop(self, hostname):
        print("RF: Disconnected from {}".format(hostname))
    def session_start(self, hostname, command):
        print("RF: Session {} started on {}".format(command, hostname))
    def session_stop(self, hostname):
        print("RF: Session ended on {}".format(hostname))
    def line(self, hostname, line):
        print(line, end="")

class ColonFormatter(Formatter):
    """
    Display each line prepended with the hostname and a ':'
    """
    def line(self, hostname, line):
        print("{}:{}".format(hostname, line))

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
