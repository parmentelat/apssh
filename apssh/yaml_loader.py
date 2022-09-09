from pathlib import Path
from platform import node
import re

import yaml

from jinja2 import Template, DebugUndefined


from asynciojobs import Scheduler
from apssh import Run, RunScript, RunString, SshJob, formatters
from apssh.nodes import SshNode

class YamlLoader:

    """
    The `YamlLoader` class builds a Scheduler object from a yaml file

    In addition to using the regular YAML syntax
    (current implementation uses pyyaml, which supports YAML v1.1)
    the input can optionnally pass through Jinja2 templating;
    to that end, provide a non-empty `env` parameter, that will specify
    templating variables

    Parameters:
      filename(str): the input file (can be a Path as well)
    """

    def __init__(self, filename):
        self.path = Path(filename)


    def load(self, env=None) -> Scheduler:
        """
        parse input filename and returns a `Scheduler` object; a shortcut to using
        `load_with_maps()` and trashing the intermediary maps

        Parameters:
          env(dict): if not empty, a Jinja2 pass is performed on the input
        """
        _nodes_map, _jobs_map, scheduler = self.load_with_maps(env)
        return scheduler


    def load_with_maps(self, env=None) -> Scheduler:
        """
        parse input filename

        Parameters:
          env(dict): if not empty, a Jinja2 pass is performed on the input

        Returns:
          a tuple containing:
            (*) nodes_map, a dictionary linking ids to SshNode instantes
            (*) jobs_map, a dictionary linking ids to Job instances
            (*) the resulting scheduler
        """
        with self.path.open() as feed:
            yaml_input = feed.read()

        if env:
            template = Template(yaml_input, undefined=DebugUndefined)
            yaml_input = template.render(**env)

        D = yaml.safe_load(yaml_input)

        if 'nodes' not in D:
            raise ValueError(f"file {self.filename} has no 'nodes' key")
        if 'jobs' not in D:
            raise ValueError(f"file {self.filename} has no 'jobs' key")

        nodes_map = self._load_nodes(D['nodes'])

        jobs_map, scheduler = self._load_jobs(D['jobs'], nodes_map)
        return nodes_map, jobs_map, scheduler


    @staticmethod
    def _dict_to_class(D, cls, mandatories, optionals):
        """
        translate a dict to a class object

        the 'id' field is always mandatory

        mandatories and optionals are both expected to be a dictionary that maps
        fieldname to a transformer function that is applied to the corresponding
        value; if None, no transformation is performed

        mandatory values are passed to the constructor

        as far as optionals, the result is then assigned right into object.key

        returns a tuple (id, obj)
        """
        assert 'id' in D

        # check for mandatories
        for key in mandatories:
            if key not in D:
                raise ValueError(f"dict {D} misses the `{key}` field")

        # check for unexpected keys
        for key in D:
            if key == 'id':
                continue
            if key not in mandatories and key not in optionals:
                raise ValueError(f"{D} contains unexpected key {key}")
        # build object from mandatories
        constructor_args = {}
        for key, transformer in mandatories.items():
            value = D[key]
            if transformer:
                value = transformer(value)
            constructor_args[key] = value
        object = cls(**constructor_args)
        # assign optionals
        for key, transformer in optionals.items():
            if key not in D:
                continue
            value = D[key]
            if transformer:
                value = transformer(value)
            setattr(object, key, value)

        return (D['id'], object)


    def _load_nodes(self, nodes_list):
        """
        returns a dict:
        - keys are the ids defined in each node (mandatory)
        - values are SshNode objects
        """
        nodes_map = {}

        def locate_node_from_id(node_id):
            return nodes_map[node_id]

        def locate_formatter(clsname):
            # formatters is the apssh.formatters module
            cls = getattr(formatters, clsname)
            return cls()

        mandatories = {
            'hostname': None,
        }
        optionals = {
            # the gateway field refers to an id defined beforehand
            'gateway': locate_node_from_id,
            'username': None,
            'critical': None,
            'formatter': None,
            'verbose': None,
        }
        for node_dict in nodes_list:
            id, node = self._dict_to_class(
                node_dict, SshNode, mandatories, optionals)
            nodes_map[id] = node

        return nodes_map

    def _load_jobs(self, jobs_list, nodes_map):

        jobs_map = {}

        def locate_node_from_id(node_id):
            return nodes_map[node_id]

        def locate_requirement(req_id_s):
            # search instance or instances of job in the current map
            if isinstance(req_id_s, str):
                return {jobs_map[req_id_s]}
            else:
                return {jobs_map[req_id] for req_id in req_id_s}

        def create_commands(commands_list):
            result = []
            for command_dict in commands_list:
                # locate the class
                import apssh
                cls = getattr(apssh, command_dict['type'])
                result.append(cls(command_dict['command'].strip()))
            return result

        mandatories = {
            'node': locate_node_from_id,
            'commands': create_commands,
        }
        optionals = {
            'required': locate_requirement,
            'critical': None,
            'verbose': None,
            'label': None,
        }

        for job_dict in jobs_list:
            id, job = self._dict_to_class(
                job_dict, SshJob, mandatories, optionals)
            jobs_map[id] = job

        scheduler = Scheduler()
        # insert jobs in scheduler
        scheduler.update(jobs_map.values())

        return jobs_map, scheduler
