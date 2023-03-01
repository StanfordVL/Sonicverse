from abc import ABCMeta, abstractmethod

from future.utils import with_metaclass


class MetricBase(with_metaclass(ABCMeta, object)):
    def start_callback(self, env, log_reader):
        pass

    def step_callback(self, env, log_reader):
        pass

    def end_callback(self, env, log_reader):
        pass

    @abstractmethod
    def gather_results(self):
        """Produce a dictionary of values for this metric, to be added onto demo information."""
        pass
