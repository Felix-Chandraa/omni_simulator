FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC
ENV ARDUPILOT_ROOT=/opt/ardupilot
ENV OMNI_WORKSPACE=/workspace/omnitrainer-sitl

RUN ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime \
    && echo "Etc/UTC" > /etc/timezone \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        tzdata \
        ca-certificates \
        git \
        wget \
        lsb-release \
        build-essential \
        g++ \
        gcc \
        make \
        gawk \
        ccache \
        pkg-config \
        libtool \
        libtool-bin \
        libxml2-dev \
        libxslt1-dev \
        libffi-dev \
        libssl-dev \
        python-is-python3 \
        python3 \
        python3-dev \
        python3-pip \
        python3-setuptools \
        python3-wheel \
        python3-venv \
        python3-pexpect \
        python3-numpy \
        python3-pyparsing \
        python3-psutil \
        python3-lxml \
        python3-yaml \
        rsync \
        xterm \
        ppp \
    && dpkg-reconfigure -f noninteractive tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --recurse-submodules --shallow-submodules \
    https://github.com/ArduPilot/ardupilot.git "${ARDUPILOT_ROOT}"

RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel packaging \
    && python3 -m pip install --no-cache-dir \
        empy==3.3.4 \
        future \
        lxml \
        pymavlink \
        pyserial \
        MAVProxy \
        geocoder \
        ptyprocess \
        dronecan \
        flake8 \
        junitparser \
        wsproto \
        tabulate \
        pyyaml \
        numpy \
        pyparsing \
        psutil

RUN cd "${ARDUPILOT_ROOT}" \
    && ./waf configure --board sitl \
    && ./waf plane

COPY docker/entrypoint.sh /usr/local/bin/omni-docker-entrypoint
RUN chmod +x /usr/local/bin/omni-docker-entrypoint

WORKDIR /opt/ardupilot
ENTRYPOINT ["/usr/local/bin/omni-docker-entrypoint"]
ENTRYPOINT ["/usr/local/bin/omni-docker-entrypoint"]