from abc import ABCMeta, abstractmethod


class BaseTerminationCondition:
    """
    Base TerminationCondition class
    Condition-specific get_termination method is implemented in subclasses
    """

    __metaclass__ = ABCMeta

    def __init__(self, config):
        self.config = config

    @abstractmethod
    def get_termination(self, task, env):
        """
        Return whether the episode should terminate. Overwritten by subclasses.

        :param task: task instance
        :param env: environment instance
        :return: done, info
        """
        raise NotImplementedError()

    def reset(self, task, env):
        """
        Termination condition-specific reset

        :param task: task instance
        :param env: environment instance
        """
        return
