# using edge to get ffmpeg-4.x
# using testing repo to get pycryptodome
FROM alpine:edge
MAINTAINER spaam

COPY dist/*.whl .

RUN set -xe \
	&& echo 'http://dl-cdn.alpinelinux.org/alpine/edge/testing' >> /etc/apk/repositories  \
    && apk add --no-cache \
	    ca-certificates \
	    python3 \
        py3-pip \
        rtmpdump \
        py3-pycryptodome \
        ffmpeg \
    && python3 -m pip install *.whl \
    && rm -f *.whl

WORKDIR /data

ENTRYPOINT ["python3", "/usr/bin/svtplay-dl"]
CMD ["--help"]