#  SONICVERSE: A Multisensory Simulation Platform for Embodied Household Agents that See and Hear

<img src="./docs/images/sonicverse.png" width="550" height="230"> <img src="./docs/images/igibson.gif" width="250" height="230"> 

SONICVERSE is a multisensory simulation platform with integrated audio-visual simulation for training household agents that can both see and hear. Built upon [iGibson](https://github.com/StanfordVL/iGibson), SONICVERSE models realistic continuous audio rendering in 3D environments in real-time. Together with a new audio-visual VR interface that allows humans to interact with agents with audio, SONICVERSE enables a series of embodied AI tasks that need audio-visual perception. With these features, we look forward to the embodied multisensory learning research that will be enabled by SONICVERSE.

### Latest Updates
[2/13/2023] We are integrating the audio simulation part to the latest [OmniGibson](https://github.com/StanfordVL/OmniGibson). Updates will be released soon.
[2/11/2023] SONICVERSE released, for details please refer to our [arxiv preprint](https://sites.google.com/view/sonicverse?pli=1). 

<!-- ### Citation
If you use iGibson or its assets and models, consider citing the following publication:

```
@misc{li2021igibson,
      title={iGibson 2.0: Object-Centric Simulation for Robot Learning of Everyday Household Tasks}, 
      author={Chengshu Li and Fei Xia and Roberto Mart\'in-Mart\'in and Michael Lingelbach and Sanjana Srivastava and Bokui Shen and Kent Vainio and Cem Gokmen and Gokul Dharan and Tanish Jain and Andrey Kurenkov and Karen Liu and Hyowon Gweon and Jiajun Wu and Li Fei-Fei and Silvio Savarese},
      year={2021},
      eprint={2108.03272},
      archivePrefix={arXiv},
      primaryClass={cs.RO}
}
``` -->
### Documentation
SONICVERSE is built upon iGibson and Resonance audio. Please first follow the documentation of iGibson to setup the environment first and then setup the Resonance audio.

The documentation for iGibson can be found here: [iGibson Documentation](http://svl.stanford.edu/igibson/docs/). It includes installation guide (including data download instructions), quickstart guide, code examples, and APIs.

The audio simulation of SONICVERSE is built upon [Resonance audio](https://resonance-audio.github.io/resonance-audio/). To install Resonance audio, please follow the steps below:

#### Core Dependencies ([pffft](https://bitbucket.org/jpommier/pffft), [eigen](https://bitbucket.org/eigen/eigen), [googletest](https://github.com/google/googletest), [SADIE Binaural Measurements](https://www.york.ac.uk/sadie-project/database_old.html))

To clone the dependencies into the repository, run:

    ./$YOUR_LOCAL_REPO/resonance_audio/third_party/clone_core_deps.sh

#### [Unity](https://unity3d.com/) Platform Dependencies ([nativeaudioplugins](https://github.com/Unity-Technologies/NativeAudioPlugins), [embree](https://github.com/embree/embree), [ogg](https://github.com/xiph/ogg), [vorbis](https://github.com/xiph/vorbis))

The Unity plugin integrates additional tools to estimate reverberation from game
geometry and to capture Ambisonic soundfields from a game scene. These features
require the Embree, libOgg and libVorbis libraries to be *prebuilt*.

To clone and build the additional Unity dependencies, run:

    ./$YOUR_LOCAL_REPO/resonance_audio/third_party/clone_build_install_unity_deps.sh

#### Build Resonance Audio API
To build the Resonance Audio into iGibson:

    ./$YOUR_LOCAL_REPO/resonance_audio/build.sh -t=RESONANCE_AUDIO_API

#### Build Resonance Audio IGibson Plugin
To build the Resonance Audio into iGibson:

    ./$YOUR_LOCAL_REPO/resonance_audio/build.sh -t=IGIBSON_PLUGIN

### Dowloading the Dataset of 3D Scenes

For instructions to download dataset, you can visit [installation guide](http://svl.stanford.edu/igibson/docs/installation.html) and [dataset download guide](http://svl.stanford.edu/igibson/docs/dataset.html).

For audio dataset, we use the sounds collected by [Soundspace dataset](https://github.com/facebookresearch/sound-spaces/blob/main/soundspaces/README.md). Please follow the instructions to download the dataset.

### Usage

For usage, please refer to the example files in Sonicverse/Sonicverse/igibson/examples/audio_system. We have tested the simulator on Linux/Windows with an Nvidia GPU with VRAM > 6.0 GB. All the experiments are conducted with a rendering frame rate of 10 Hz and an audio sampling rate of 48000 Hz. Other configuration may also work.

To train agents, please refer to the third example in audio_system_example.py. First, an environment is created with example_config.yaml. Then, by giving actions at each timestep, the environment will return state(observations), reward, done signal, and related infos. By collecting these data, a model can be trained for robot navigation.

The environment includes a scene, a task, a robot, a sound source. These features can be set in the example_config.yaml. In the example, we use the iGibson scene called 'Rs_int'. We set the task to be AudioGoal, which is to let the robot reach the target based on audio inputs. The sound source is specified in the task as the telephone sound. The reward and termination conditions can also be set in the task. The robot is generated as a Turtlebot, and is able to receive depth inputs, audio inputs, self-states, and collision signal.

By creating new tasks under igibson/tasks/, you would be able defined your own goals for the robot to achieve. You are also free to play with different robots, sensors, sound sources, and scenes.

### Contributing
This is the github repository for SONICVERSE release. Bug reports, suggestions for improvement, as well as community developments are encouraged and appreciated. Please, consider creating an issue or sending us an email. 
