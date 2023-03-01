import argparse
import datetime
import logging
import os
import tempfile
from collections import OrderedDict

import numpy as np

import igibson
from igibson.envs.igibson_env import iGibsonEnv
from igibson.render.mesh_renderer.mesh_renderer_cpu import MeshRendererSettings
from igibson.utils.ig_logging import IGLogWriter
from igibson.utils.utils import parse_config

PHYSICS_WARMING_TIMESTEPS = 200
POST_SUCCESS_STEPS = 200


def main(selection="user", headless=False, short_exec=False):
    """
    Example of how to save a demo of a task
    """
    print("*" * 80 + "\nDescription:" + main.__doc__ + "*" * 80)

    # Assuming that if selection!="user", headless=True, short_exec=True, we are calling it from tests and we
    # do not want to parse args (it would fail because the calling function is pytest "testfile.py")
    if not (selection != "user" and headless and short_exec):
        args = parse_args()
        collect_demo(
            args.scene,
            args.task,
            args.task_id,
            args.instance_id,
            args.demo_file,
            args.disable_save,
            args.disable_scene_cache,
            args.mode,
            args.profile,
            args.config_file,
            short_exec=headless,
        )

    else:
        collect_demo(
            "Benevolence_1_int",
            "cleaning_out_drawers",
            demo_file=os.path.join("/", "tmp", "demo.hdf5"),
            short_exec=headless,
        )


def parse_args():
    scene_choices = [
        "Beechwood_0_int",
        "Beechwood_1_int",
        "Benevolence_0_int",
        "Benevolence_1_int",
        "Benevolence_2_int",
        "Ihlen_0_int",
        "Ihlen_1_int",
        "Merom_0_int",
        "Merom_1_int",
        "Pomaria_0_int",
        "Pomaria_1_int",
        "Pomaria_2_int",
        "Rs_int",
        "Wainscott_0_int",
        "Wainscott_1_int",
    ]

    task_id_choices = [0, 1]
    parser = argparse.ArgumentParser(description="Run and collect a demo of a task")
    parser.add_argument(
        "--scene",
        type=str,
        choices=scene_choices,
        default="Rs_int",
        nargs="?",
        help="Scene name/ID matching iGibson interactive scenes.",
    )
    parser.add_argument(
        "--task",
        type=str,
        required=False,
        default="cleaning_out_drawers",
        nargs="?",
        help="Name of task to collect a demo of. If it a BEHAVIOR activity, the name should be one of the official"
        " activity labels, matching one of the folders in the BDDL repository.",
    )
    parser.add_argument(
        "--task_id",
        type=int,
        required=False,
        default=0,
        choices=task_id_choices,
        nargs="?",
        help="[Only for BEHAVIOR activities] Integer ID identifying the BDDL definition of the BEHAVIOR activity. "
        "Since we only provide two definitions per activity, the ID should be 0 or 1.",
    )
    parser.add_argument(
        "--instance_id",
        type=int,
        required=False,
        default=0,
        help="[Only for BEHAVIOR activities] Instance of BEHAVIOR activity (particular URDF corresponding to "
        "an instantiation of a BDDL activity definition)",
    )
    demo_file = os.path.join(tempfile.gettempdir(), "demo.hdf5")
    parser.add_argument(
        "--demo_file", type=str, default=demo_file, required=False, help="Path (and filename) of demo file"
    )
    parser.add_argument("--disable_save", action="store_true", help="Whether to disable saving logfiles.")
    parser.add_argument(
        "--disable_scene_cache", action="store_true", help="Whether to disable using pre-initialized scene caches."
    )
    parser.add_argument("--profile", action="store_true", help="Whether to print profiling data.")
    parser.add_argument(
        "--config_file",
        help="which config file to use [default: use yaml files in examples/configs]",
        default=os.path.join(igibson.configs_path, "behavior_robot_vr_behavior_task.yaml"),
        required=False,
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["headless", "headless_tensor", "vr", "gui_non_interactive"],
        help="Mode for replaying",
        default="headless",
    )
    return parser.parse_args()


def collect_demo(
    scene,
    task,
    task_id=0,
    instance_id=0,
    demo_file=None,
    disable_save=False,
    disable_scene_cache=False,
    mode="headless",
    profile=False,
    config_file=os.path.join(igibson.configs_path, "behavior_robot_vr_behavior_task.yaml"),
    short_exec=False,
):
    """ """
    # HDR files for PBR rendering
    hdr_texture = os.path.join(igibson.ig_dataset_path, "scenes", "background", "probe_02.hdr")
    hdr_texture2 = os.path.join(igibson.ig_dataset_path, "scenes", "background", "probe_03.hdr")
    light_modulation_map_filename = os.path.join(
        igibson.ig_dataset_path, "scenes", "Rs_int", "layout", "floor_lighttype_0.png"
    )
    background_texture = os.path.join(igibson.ig_dataset_path, "scenes", "background", "urban_street_01.jpg")

    rendering_settings = MeshRendererSettings(
        optimized=True,
        fullscreen=False,
        env_texture_filename=hdr_texture,
        env_texture_filename2=hdr_texture2,
        env_texture_filename3=background_texture,
        light_modulation_map_filename=light_modulation_map_filename,
        enable_shadow=True,
        enable_pbr=True,
        msaa=False,
        light_dimming_factor=1.0,
    )

    config = parse_config(config_file)
    config["task"] = task
    config["task_id"] = task_id
    config["scene_id"] = scene
    config["instance_id"] = instance_id
    config["online_sampling"] = disable_scene_cache
    config["load_clutter"] = True
    if short_exec:
        config["max_step"] = 500

    env = iGibsonEnv(
        config_file=config,
        mode=mode,
        action_timestep=1 / 30.0,
        physics_timestep=1 / 300.0,
        rendering_settings=rendering_settings,
    )
    env.reset()
    robot = env.robots[0]

    log_writer = None
    if not disable_save:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if demo_file is None:
            demo_file = "{}_{}_{}_{}_{}.hdf5".format(task, task_id, scene, instance_id, timestamp)
        log_writer = IGLogWriter(
            env.simulator,
            log_filepath=demo_file,
            task=env.task,
            store_vr=False,
            vr_robot=robot,
            profiling_mode=profile,
            filter_objects=True,
        )
        log_writer.set_up_data_storage()
        log_writer.hf.attrs["/metadata/instance_id"] = instance_id

    # Main recording loop
    done = False
    steps_after_success = 0
    while not done:
        if env.current_step < PHYSICS_WARMING_TIMESTEPS:
            action = np.zeros(robot.action_dim)
        elif mode == "vr":
            action = env.simulator.gen_vr_robot_action()
        else:
            action = np.random.uniform(-0.01, 0.01, size=(robot.action_dim,))

        # Execute the action
        state, reward, done, info = env.step(action)
        success = info["success"]

        if log_writer and not disable_save:
            log_writer.process_frame()

        # Time out
        if done and not success:
            break

        if success:
            steps_after_success += 1
        else:
            steps_after_success = 0

        # Consecutive success for POST_SUCCESS_STEPS steps
        if steps_after_success >= POST_SUCCESS_STEPS:
            break

    assert env.current_step > PHYSICS_WARMING_TIMESTEPS, "No actions were applied."

    if log_writer and not disable_save:
        log_writer.end_log_session()

    env.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
