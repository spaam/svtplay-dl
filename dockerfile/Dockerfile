# using edge to get ffmpeg-4.x
FROM alpine:edge
MAINTAINER spaam

COPY dist/*.whl .

RUN set -xe \
    && apk add --no-cache \
	    ca-certificates \
	    python3 \
        py3-pip \
        rtmpdump \
        py3-cryptography \
        ffmpeg \
    && python3 -m pip install *.whl \
    && rm -f *.whl

WORKDIR /data

ENTRYPOINT ["python3", "/usr/bin/svtplay-dl"]
CMD ["--help"]
