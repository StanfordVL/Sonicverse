from nvidia/cudagl:10.0-base-ubuntu18.04

ARG CUDA=10.0
ARG CUDNN=7.6.2.24-1

RUN apt-get update  && apt-get install -y --no-install-recommends \
	curl build-essential git cmake \
	cuda-command-line-tools-10-0 \
    cuda-cublas-10-0 \
    cuda-cufft-10-0 \
    cuda-curand-10-0 \
    cuda-cusolver-10-0 \
    cuda-cusparse-10-0 \
    libcudnn7=${CUDNN}+cuda${CUDA} \
    vim \
    tmux \
    libhdf5-dev \
    libsm6 \
    libxext6 \
    libxrender-dev \
    wget

# Install miniconda to /miniconda
RUN curl -LO http://repo.continuum.io/miniconda/Miniconda-latest-Linux-x86_64.sh
RUN bash Miniconda-latest-Linux-x86_64.sh -p /miniconda -b
RUN rm Miniconda-latest-Linux-x86_64.sh
ENV PATH=/miniconda/bin:${PATH}

RUN conda update -y conda
RUN conda create -y -n igibson python=3.7

ENV PATH /miniconda/envs/igibson/bin:$PATH

# NOTE: This needs to be updated in-step with the base cudagl image so the tensor renderer works
RUN pip install tensorflow-gpu==1.15.0

RUN git clone --depth 1 https://github.com/StanfordVL/iGibson /opt/iGibson --recursive

WORKDIR /opt/iGibson
RUN pip install --no-cache-dir -e .

RUN git clone https://github.com/StanfordVL/agents/ /opt/agents

WORKDIR /opt/agents
RUN pip install -e .

RUN pip install --no-cache-dir pytest

RUN python3 -m igibson.utils.assets_utils --download_assets && rm -rf /tmp/*
RUN python3 -m igibson.utils.assets_utils --download_demo_data && rm -rf /tmp/*

WORKDIR /opt/iGibson/igibson/examples
