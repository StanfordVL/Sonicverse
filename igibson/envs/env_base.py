import logging

import gym
import cv2
import numpy as np
import copy
from igibson.utils.mesh_util import ortho
from igibson.audio.audio_system import AudioSystem
import igibson.audio.default_config as default_audio_config
from igibson.audio.ig_acoustic_mesh import getIgAcousticMesh
from igibson.audio.matterport_acoustic_mesh import getMatterportAcousticMesh
from igibson.object_states import AABB
from igibson.object_states.utils import detect_closeness
from igibson.render.mesh_renderer.mesh_renderer_settings import MeshRendererSettings
from igibson.render.mesh_renderer.mesh_renderer_vr import VrSettings
from igibson.robots import REGISTERED_ROBOTS
from igibson.scenes.empty_scene import EmptyScene
from igibson.scenes.gibson_indoor_scene import StaticIndoorScene
from igibson.scenes.igibson_indoor_scene import InteractiveIndoorScene
from igibson.scenes.stadium_scene import StadiumScene
from igibson.simulator import Simulator
from igibson.simulator_vr import SimulatorVR
from igibson.utils.utils import parse_config

log = logging.getLogger(__name__)


class BaseEnv(gym.Env):
    """
    Base Env class that handles loading scene and robot, following OpenAI Gym interface.
    Functions like reset and step are not implemented.
    """

    def __init__(
        self,
        config_file,
        scene_id=None,
        mode="headless",
        action_timestep=1 / 10.0,
        physics_timestep=1 / 240.0,
        rendering_settings=None,
        vr_settings=None,
        device_idx=0,
        use_pb_gui=False,
    ):
        """
        :param config_file: config_file path
        :param scene_id: override scene_id in config file
        :param mode: headless, headless_tensor, gui_interactive, gui_non_interactive, vr
        :param action_timestep: environment executes action per action_timestep second
        :param physics_timestep: physics timestep for pybullet
        :param rendering_settings: rendering_settings to override the default one
        :param vr_settings: vr_settings to override the default one
        :param device_idx: device_idx: which GPU to run the simulation and rendering on
        :param use_pb_gui: concurrently display the interactive pybullet gui (for debugging)
        """
        self.config = parse_config(config_file)
        if scene_id is not None:
            self.config["scene_id"] = scene_id

        self.mode = mode
        self.action_timestep = action_timestep
        self.physics_timestep = physics_timestep
        self.rendering_settings = rendering_settings
        self.vr_settings = vr_settings
        self.texture_randomization_freq = self.config.get("texture_randomization_freq", None)
        self.object_randomization_freq = self.config.get("object_randomization_freq", None)
        self.object_randomization_idx = 0
        self.num_object_randomization_idx = 10
        self.audio_system = None

        default_enable_shadows = False  # What to do if it is not specified in the config file
        enable_shadow = self.config.get("enable_shadow", default_enable_shadows)
        default_enable_pbr = False  # What to do if it is not specified in the config file
        enable_pbr = self.config.get("enable_pbr", default_enable_pbr)
        texture_scale = self.config.get("texture_scale", 1.0)

        if self.rendering_settings is None:
            # TODO: We currently only support the optimized renderer due to some issues with obj highlighting.
            self.rendering_settings = MeshRendererSettings(
                enable_shadow=enable_shadow,
                enable_pbr=enable_pbr,
                msaa=False,
                texture_scale=texture_scale,
                optimized=self.config.get("optimized_renderer", True),
                load_textures=self.config.get("load_texture", True),
                hide_robot=self.config.get("hide_robot", True),
            )

        if mode == "vr":
            if self.vr_settings is None:
                self.vr_settings = VrSettings(use_vr=True)
            self.simulator = SimulatorVR(
                physics_timestep=physics_timestep,
                render_timestep=action_timestep,
                image_width=self.config.get("image_width", 128),
                image_height=self.config.get("image_height", 128),
                vertical_fov=self.config.get("vertical_fov", 90),
                device_idx=device_idx,
                rendering_settings=self.rendering_settings,
                vr_settings=self.vr_settings,
                use_pb_gui=use_pb_gui,
            )
        else:
            self.simulator = Simulator(
                mode=mode,
                physics_timestep=physics_timestep,
                render_timestep=action_timestep,
                image_width=self.config.get("image_width", 128) if len(self.config["VIDEO_OPTION"])==0 \
                                                        else self.config.get("image_width_video", 128),
                image_height=self.config.get("image_height", 128) if len(self.config["VIDEO_OPTION"])==0 \
                                                        else self.config.get("image_height_video", 128),
                vertical_fov=self.config.get("vertical_fov", 90),
                device_idx=device_idx,
                rendering_settings=self.rendering_settings,
                use_pb_gui=use_pb_gui,
            )
        self.load()

    def reload(self, config_file):
        """
        Reload another config file.
        This allows one to change the configuration on the fly.

        :param config_file: new config file path
        """
        self.config = parse_config(config_file)
        self.simulator.reload()
        self.load()

    def reload_model(self, scene_id):
        """
        Reload another scene model.
        This allows one to change the scene on the fly.

        :param scene_id: new scene_id
        """
        self.config["scene_id"] = scene_id
        self.simulator.reload()
        self.load()

    def reload_model_object_randomization(self):
        """
        Reload the same model, with the next object randomization random seed.
        """
        if self.object_randomization_freq is None:
            return
        self.object_randomization_idx = (self.object_randomization_idx + 1) % (self.num_object_randomization_idx)
        self.simulator.reload()
        self.load()

    def load(self):
        """
        Load the scene and robot specified in the config file.
        """
        if "scene_id" not in self.config:
            return
        if self.config["scene"] == "empty":
            scene = EmptyScene()
        elif self.config["scene"] == "stadium":
            scene = StadiumScene()
        elif self.config["scene"] == "gibson":
            scene = StaticIndoorScene(
                self.config["scene_id"],
                waypoint_resolution=self.config.get("waypoint_resolution", 0.2),
                num_waypoints=self.config.get("num_waypoints", 10),
                build_graph=self.config.get("build_graph", False),
                trav_map_resolution=self.config.get("trav_map_resolution", 0.1),
                trav_map_erosion=self.config.get("trav_map_erosion", 2),
                pybullet_load_texture=self.config.get("pybullet_load_texture", False),
            )
        elif self.config["scene"] == "igibson":
            urdf_file = self.config.get("urdf_file", None)
            if urdf_file is None and not self.config.get("online_sampling", True):
                urdf_file = "{}_task_{}_{}_{}_fixed_furniture".format(
                    self.config["scene_id"],
                    self.config["task"],
                    self.config["task_id"],
                    self.config["instance_id"],
                )
            include_robots = self.config.get("include_robots", True)
            scene = InteractiveIndoorScene(
                self.config["scene_id"],
                urdf_file=urdf_file,
                waypoint_resolution=self.config.get("waypoint_resolution", 0.2),
                num_waypoints=self.config.get("num_waypoints", 10),
                build_graph=self.config.get("build_graph", False),
                trav_map_resolution=self.config.get("trav_map_resolution", 0.1),
                trav_map_erosion=self.config.get("trav_map_erosion", 2),
                trav_map_type=self.config.get("trav_map_type", "with_obj"),
                texture_randomization=self.texture_randomization_freq is not None,
                object_randomization=self.object_randomization_freq is not None,
                object_randomization_idx=self.object_randomization_idx,
                should_open_all_doors=self.config.get("should_open_all_doors", False),
                load_object_categories=self.config.get("load_object_categories", None),
                not_load_object_categories=self.config.get("not_load_object_categories", None),
                load_room_types=self.config.get("load_room_types", None),
                load_room_instances=self.config.get("load_room_instances", None),
                merge_fixed_links=self.config.get("merge_fixed_links", True)
                and not self.config.get("online_sampling", False),
                include_robots=include_robots,
            )
            # TODO: Unify the function import_scene and take out of the if-else clauses.
            first_n = self.config.get("_set_first_n_objects", -1)
            if first_n != -1:
                scene._set_first_n_objects(first_n)
        self.simulator.import_scene(scene)

        # Get robot config
        robot_config = self.config["robot"]
        self.robot_config_ = copy.deepcopy(robot_config)

        # If no robot has been imported from the scene
        if len(scene.robots) == 0:
            # Get corresponding robot class
            robot_name = robot_config.pop("name")
            assert robot_name in REGISTERED_ROBOTS, "Got invalid robot to instantiate: {}".format(robot_name)
            robot = REGISTERED_ROBOTS[robot_name](**robot_config)

            self.simulator.import_object(robot)
            # The scene might contain cached agent pose
            # By default, we load the agent pose that matches the robot name (e.g. Fetch, BehaviorRobot)
            # The user can also specify "agent_pose" in the config file to use the cached agent pose for any robot
            # For example, the user can load a BehaviorRobot and place it at Fetch's agent pose
            agent_pose_name = self.config.get("agent_pose", robot_name)
            if isinstance(scene, InteractiveIndoorScene) and agent_pose_name in scene.agent_poses:
                pos, orn = scene.agent_poses[agent_pose_name]

                if agent_pose_name != robot_name:
                    # Need to change the z-pos - assume we always want to place the robot bottom at z = 0
                    lower, _ = robot.states[AABB].get_value()
                    pos[2] = -lower[2]

                robot.set_position_orientation(pos, orn)

                if any(
                    detect_closeness(
                        bid, exclude_bodyB=scene.objects_by_category["floors"][0].get_body_ids(), distance=0.01
                    )
                    for bid in robot.get_body_ids()
                ):
                    log.warning("Robot's cached initial pose has collisions.")

        self.scene = scene
        self.robots = scene.robots

        if self.config['scene'] == 'gibson':
            sem_map_path = self.config.get('scene_sem_map_dir', "")
            if not sem_map_path:
                raise ValueError("Config must specify a valid scene_sem_map_dir as a path that contains {scene_id}/sem_map.png")
            acousticMesh = getMatterportAcousticMesh(self.simulator, sem_map_path + self.config['scene_id']+"/sem_map.png")
        elif self.config['scene'] == 'igibson':
            acousticMesh = getIgAcousticMesh(self.simulator)
        else:
            raise ValueError("Audio-enabled Envs only compatible with Gibson and iGibson scenes")
        if self.audio_system is not None:
            self.audio_system.disconnect()
        self.audio_system = AudioSystem(self.simulator, self.robots[0], acousticMesh, 
                                        is_Viewer=False, writeToFile=self.config.get('AUDIO_DIR', ""), SR = 44100,
                                        occl_multiplier=self.config.get('occl_multiplier', default_audio_config.OCCLUSION_MULTIPLIER),
                                        spectrogram_window_len=self.config.get('spectrogram_window_len', default_audio_config.SPECTROGRAM_WINDOW_LEN),
                                        renderAmbisonics=self.config.get('ambisonic_sensor', False), stream_input=self.config.get('VR_audio_source', False), is_Sim2Real=self.config.get('is_Sim2Real', False))

    def clean(self):
        """
        Clean up the environment.
        """
        if self.simulator is not None:
            self.simulator.disconnect()

        if self.audio_system is not None:
            self.audio_system.disconnect()

    def close(self):
        """
        Synonymous function with clean.
        """
        self.clean()

    def simulator_step(self):
        """
        Step the simulation.
        This is different from environment step that returns the next
        observation, reward, done, info.
        """
        self.simulator.step()
        self.audio_system.step()

    def step(self, action):
        """
        Overwritten by subclasses.
        """
        return NotImplementedError()

    def reset(self):
        """
        Overwritten by subclasses.
        """
        return NotImplementedError()

