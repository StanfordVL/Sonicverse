from abc import abstractmethod

import gym
import numpy as np

from igibson.robots.locomotion_robot import LocomotionRobot


class TwoWheelRobot(LocomotionRobot):
    """
    Robot that is is equipped with locomotive (navigational) capabilities, as defined by two wheels that can be used
    for differential drive (e.g.: Turtlebot).
    Provides common interface for a wide variety of robots.

    NOTE: controller_config should, at the minimum, contain:
        base: controller specifications for the controller to control this robot's base (locomotion).
            Should include:

            - name: Controller to create
            - <other kwargs> relevant to the controller being created. Note that all values will have default
                values specified, but setting these individual kwargs will override them
    """

    def _validate_configuration(self):
        # Make sure base only has two indices (i.e.: two wheels for differential drive)
        assert len(self.base_control_idx) == 2, "Differential drive can only be used with robot with two base joints!"

        # run super
        super()._validate_configuration()

    def _create_discrete_action_space(self):
        # Set action list based on controller (joint or DD) used

        # We set straight velocity to be 50% of max velocity for the wheels
        max_wheel_joint_vels = self.control_limits["velocity"][1][self.base_control_idx]
        assert len(max_wheel_joint_vels) == 2, "TwoWheelRobot must only have two base (wheel) joints!"
        assert max_wheel_joint_vels[0] == max_wheel_joint_vels[1], "Both wheels must have the same max speed!"
        wheel_straight_vel = 0.5 * max_wheel_joint_vels[0]
        wheel_rotate_vel = 0.5
        if self.controller_config["base"]["name"] == "JointController":
            action_list = [
                [wheel_straight_vel, wheel_straight_vel],
                [-wheel_straight_vel, -wheel_straight_vel],
                [wheel_rotate_vel, -wheel_rotate_vel],
                [-wheel_rotate_vel, wheel_rotate_vel],
#                 [0, 0],
            ]
        else:
            # DifferentialDriveController
            lin_vel = wheel_straight_vel * self.wheel_radius
            ang_vel = wheel_rotate_vel * self.wheel_radius * 2.0 / self.wheel_axle_length
            action_list = [
                [lin_vel, 0],
                [-lin_vel, 0],
                [0, ang_vel],
                [0, -ang_vel],
#                 [0, 0],
            ]

        self.action_list = action_list

        # Return this action space
        return gym.spaces.Discrete(len(self.action_list))

    def _get_proprioception_dict(self):
        dic = super()._get_proprioception_dict()

        # Grab wheel joint velocity info
        joints = list(self._joints.values())
        wheel_joints = [joints[idx] for idx in self.base_control_idx]
        l_vel, r_vel = [jnt.get_state()[1] for jnt in wheel_joints]

        # Compute linear and angular velocities
        lin_vel = (l_vel + r_vel) / 2.0 * self.wheel_radius
        ang_vel = (r_vel - l_vel) / self.wheel_axle_length

        # Add info
        dic["dd_base_lin_vel"] = np.array([lin_vel])
        dic["dd_base_ang_vel"] = np.array([ang_vel])

        return dic

    @property
    def default_proprio_obs(self):
        obs_keys = super().default_proprio_obs
        return obs_keys + ["dd_base_lin_vel", "dd_base_ang_vel"]

    @property
    def _default_controllers(self):
        # Always call super first
        controllers = super()._default_controllers

        # Use DifferentialDrive as default
        controllers["base"] = "DifferentialDriveController"

        return controllers

    @property
    def _default_base_differential_drive_controller_config(self):
        """
        :return: Dict[str, Any] Default differential drive controller config to
            control this robot's base.
        """
        return {
            "name": "DifferentialDriveController",
            "control_freq": self.control_freq,
            "wheel_radius": self.wheel_radius,
            "wheel_axle_length": self.wheel_axle_length,
            "control_limits": self.control_limits,
            "joint_idx": self.base_control_idx,
        }

    @property
    def _default_controller_config(self):
        # Always run super method first
        cfg = super()._default_controller_config

        # Add differential drive option to base
        cfg["base"][
            self._default_base_differential_drive_controller_config["name"]
        ] = self._default_base_differential_drive_controller_config

        return cfg

    @property
    @abstractmethod
    def wheel_radius(self):
        """
        :return: float, radius of each wheel at the base, in metric units
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def wheel_axle_length(self):
        """
        :return: float, perpendicular distance between the robot's two wheels, in metric units
        """
        raise NotImplementedError
