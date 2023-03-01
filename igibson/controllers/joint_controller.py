import numpy as np
import pybullet as p

from igibson.controllers import ControlType, LocomotionController, ManipulationController
from igibson.utils.python_utils import assert_valid_key


class JointController(LocomotionController, ManipulationController):
    """
    Controller class for joint control. Because pybullet can handle direct position / velocity / torque
    control signals, this is merely a pass-through operation from command to control (with clipping / scaling built in).

    Each controller step consists of the following:
        1. Clip + Scale inputted command according to @command_input_limits and @command_output_limits
        2a. If using delta commands, then adds the command to the current joint state
        2b. Clips the resulting command by the motor limits
    """

    def __init__(
        self,
        control_freq,
        motor_type,
        control_limits,
        joint_idx,
        command_input_limits="default",
        command_output_limits="default",
        parallel_mode=False,
        inverted=False,
        use_delta_commands=False,
        compute_delta_in_quat_space=[],
    ):
        """
        :param control_freq: int, controller loop frequency
        :param motor_type: str, type of motor being controlled, one of {position, velocity, torque}
        :param control_limits: Dict[str, Tuple[Array[float], Array[float]]]: The min/max limits to the outputted
            control signal. Should specify per-actuator type limits, i.e.:

            "position": [[min], [max]]
            "velocity": [[min], [max]]
            "torque": [[min], [max]]
            "has_limit": [...bool...]

            Values outside of this range will be clipped, if the corresponding joint index in has_limit is True.
        :param joint_idx: Array[int], specific joint indices controlled by this robot. Used for inferring
            controller-relevant values during control computations
        :param command_input_limits: None or "default" or Tuple[float, float] or Tuple[Array[float], Array[float]],
            if set, is the min/max acceptable inputted command. Values outside of this range will be clipped.
            If None, no clipping will be used. If "default", range will be set to (-1, 1)
        :param command_output_limits: None or "default" or Tuple[float, float] or Tuple[Array[float], Array[float]], if set,
            is the min/max scaled command. If both this value and @command_input_limits is not None,
            then all inputted command values will be scaled from the input range to the output range.
            If either is None, no scaling will be used. If "default", then this range will automatically be set
            to the @control_limits entry corresponding to self.control_type
        :param parallel_mode: bool, indicating whether the controller should accept a single input and scale it
            appropriately for each joint (True), or accept a separate input for each joint (False).
        :param inverted: bool, indicating whether the inputs should be mapped to outputs directly or in the inverse
            direction (e.g. high command => low control).
        :param use_delta_commands: bool, whether inputted commands should be interpreted as delta or absolute values
        :param compute_delta_in_quat_space: List[(rx_idx, ry_idx, rz_idx), ...], groups of joints that need to be
            processed in quaternion space to avoid gimbal lock issues normally faced by 3 DOF rotation joints. Each
            group needs to consist of three idxes corresponding to the indices in the input space. This is only
            used in the delta_commands mode.
        """
        # Store arguments
        assert_valid_key(key=motor_type.lower(), valid_keys=ControlType.VALID_TYPES_STR, name="motor_type")
        self.motor_type = motor_type.lower()
        self.parallel_mode = parallel_mode
        self.use_delta_commands = use_delta_commands
        self.compute_delta_in_quat_space = compute_delta_in_quat_space

        # When in delta mode, it doesn't make sense to infer output range using the joint limits (since that's an
        # absolute range and our values are relative). So reject the default mode option in that case.
        assert not (
            self.use_delta_commands and command_output_limits == "default"
        ), "Cannot use 'default' command output limits in delta commands mode of JointController. Try None instead."

        # Run super init
        super().__init__(
            control_freq=control_freq,
            control_limits=control_limits,
            joint_idx=joint_idx,
            command_input_limits=command_input_limits,
            command_output_limits=command_output_limits,
            inverted=inverted,
        )

    def reset(self):
        # Nothing to reset.
        pass

    def _command_to_control(self, command, control_dict):
        """
        Converts the (already preprocessed) inputted @command into deployable (non-clipped!) joint control signal

        :param command: Array[float], desired (already preprocessed) command to convert into control signals
        :param control_dict: Dict[str, Any], dictionary that should include any relevant keyword-mapped
            states necessary for controller computation. Must include the following keys:
                joint_position: Array of current joint positions
                joint_velocity: Array of current joint velocities
                joint_torque: Array of current joint torques

        :return: Array[float], outputted (non-clipped!) control signal to deploy
        """
        # If we're using delta commands, add this value
        if self.use_delta_commands:
            # Compute the base value for the command.
            base_value = control_dict["joint_{}".format(self.motor_type)][self.joint_idx]

            # Apply the command to the base value.
            u = base_value + command

            # Correct any gimbal lock issues using the compute_delta_in_quat_space group.
            for rx_ind, ry_ind, rz_ind in self.compute_delta_in_quat_space:
                # Grab the starting rotations of these joints.
                start_rots = base_value[[rx_ind, ry_ind, rz_ind]]

                # Grab the delta rotations.
                delta_rots = command[[rx_ind, ry_ind, rz_ind]]

                # Compute the final rotations in the quaternion space.
                _, end_quat = p.multiplyTransforms(
                    [0, 0, 0], p.getQuaternionFromEuler(delta_rots), [0, 0, 0], p.getQuaternionFromEuler(start_rots)
                )
                end_rots = p.getEulerFromQuaternion(end_quat)

                # Update the command
                u[[rx_ind, ry_ind, rz_ind]] = end_rots

        # Otherwise, control is simply the command itself
        else:
            u = command

        # Return control
        return u

    @property
    def control_type(self):
        return ControlType.get_type(type_str=self.motor_type)

    @property
    def command_dim(self):
        return 1 if self.parallel_mode else len(self.joint_idx)
