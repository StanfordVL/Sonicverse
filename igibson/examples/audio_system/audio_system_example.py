import numpy as np
from igibson.simulator import Simulator
from igibson.scenes.igibson_indoor_scene import InteractiveIndoorScene, StaticIndoorScene
from igibson.objects import cube
from igibson.audio.ig_acoustic_mesh import getIgAcousticMesh
from igibson.audio.matterport_acoustic_mesh import getMatterportAcousticMesh
from igibson.envs.igibson_env import iGibsonEnv
from igibson.audio.audio_system import AudioSystem
import pyaudio

def ig_example():
    # streaming audio in an iGibson scene
    
    s = Simulator(mode='gui_interactive', image_width=512, image_height=512, device_idx=0)
    scene = InteractiveIndoorScene('Rs_int', texture_randomization=False, object_randomization=False)
    s.import_scene(scene)

    obj_id = (scene.objects_by_category["loudspeaker"][0]).get_body_ids()[0]

    acousticMesh = getIgAcousticMesh(s)

    # Audio System Initialization!
    audioSystem = AudioSystem(s, s.viewer, acousticMesh, is_Viewer=True, writeToFile="example")
    # Attach wav file to imported cube obj
    audioSystem.registerSource(obj_id, "440Hz_44100Hz.wav", enabled=True)

    # Visualize reverb probes!
    for i in range(len(scene.floor_heights)):
        for probe_pos in audioSystem.probe_key_to_pos_by_floor[i].values():
            z = scene.floor_heights[i] + 1.7
            pos = [probe_pos[0], probe_pos[1], z]
            obj = cube.Cube(pos=pos, dim=[0.1, 0.1, 0.1], visual_only=True, mass=0, color=[255, 0, 0, 1])
            s.import_object(obj)

    # This section is entirely optional - it simply tries to stream audio live
    def pyaudCallback(in_data, frame_count, time_info, status):
        return (bytes(audioSystem.current_output), pyaudio.paContinue)
    pyaud = pyaudio.PyAudio()
    stream = pyaud.open(rate=audioSystem.SR, frames_per_buffer=audioSystem.framesPerBuf, format=pyaudio.paInt16, channels=2, output=True, stream_callback=pyaudCallback)

    for i in range(1000):
        s.step()
        audioSystem.step()
    audioSystem.disconnect()
    s.disconnect()
    
def mp3d_example():
    # streaming audio in an mp3d scene
    
    s = Simulator(mode='gui_interactive', image_width=512, image_height=512, device_idx=0)
    scene = StaticIndoorScene('17DRP5sb8fy')
    s.import_scene(scene)

    acousticMesh = getMatterportAcousticMesh(s, "matterport3d-downsized/v2/17DRP5sb8fy/sem_map.png")

    obj = cube.Cube(pos=[0, 0, 2], dim=[0.3, 0.3, 0.3], visual_only=True, mass=0, color=[1,1,0,1])
    s.import_object(obj)
    obj_id = obj.get_body_id()
    # Audio System Initialization!
    audioSystem = AudioSystem(s, s.viewer, acousticMesh, is_Viewer=True, writeToFile="example")
    # Attach wav file to imported cube obj
    audioSystem.registerSource(obj_id, "440Hz_44100Hz.wav", enabled=True)
    # Ensure source continuously repeats
    audioSystem.setSourceRepeat(obj_id)

    # Visualize reverb probes!
    for i in range(len(scene.floor_heights)):
        for probe_pos in audioSystem.probe_key_to_pos_by_floor[i].values():
            z = scene.floor_heights[i] + 1.7
            pos = [probe_pos[0], probe_pos[1], z]
            obj = cube.Cube(pos=pos, dim=[0.1, 0.1, 0.1], visual_only=True, mass=0, color=[255, 0, 0, 1])
            s.import_object(obj)

    # This section is entirely optional - it simply tries to stream audio live
    def pyaudCallback(in_data, frame_count, time_info, status):
        return (bytes(audioSystem.current_output), pyaudio.paContinue)
    pyaud = pyaudio.PyAudio()
    stream = pyaud.open(rate=audioSystem.SR, frames_per_buffer=audioSystem.framesPerBuf, format=pyaudio.paInt16, channels=2, output=True, stream_callback=pyaudCallback)

    for i in range(4000):
        s.step()
        audioSystem.step()

    audioSystem.disconnect()
    s.disconnect()

def agent_example():
    # setup a turtlebot and let it navigate in the environment, the turtlebot is the listener
    
    exp_config = "example_config.yaml"
    env = iGibsonEnv(config_file=exp_config, mode='headless', scene_id='Rs_int')
    env.reset()

    # let agent move forward for 50 actions(5 seconds)
    # observations are available in states at each frame
    # audio will be saved to AUDIO_DIR after run
    for i in range(50):
        state, _,_,_ = env.step(np.array([0.1,0.1]))
    env.audio_system.disconnect()
    env.simulator.disconnect()
    
def main():
    #mp3d_example()
    #ig_example()
    agent_example()

if __name__ == '__main__':
    main()