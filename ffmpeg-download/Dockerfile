FROM registry.cn-hangzhou.aliyuncs.com/jcleng/library-alpine:3.20.1
USER root
COPY --from=registry.cn-hangzhou.aliyuncs.com/jcleng/library-docker:24.0.9-cli /usr/local/bin/docker /usr/local/bin/docker
ADD https://busybox.net/downloads/binaries/1.21.1/busybox-x86_64 /bin/busybox_new
RUN chmod +x /bin/busybox_new && mv /bin/busybox_new /bin/busybox
ADD https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz /tmp/ffmpeg.tar.xz
RUN tar -xf /tmp/ffmpeg.tar.xz -C /tmp && \
    mv /tmp/ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ && \
    mv /tmp/ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ && \
    rm -rf /tmp/ffmpeg*
WORKDIR /app
COPY cgi-bin/ /app/cgi-bin/
RUN mkdir -p /app/downloads && chmod 777 /app/downloads
ENV FFMPEG_USER=admin
ENV FFMPEG_PASS=admin
ENV FFMPEG_DL_DIR=/app/downloads
EXPOSE 33001
CMD ["busybox", "httpd", "-v", "-f", "-p", "33001", "-h", "."]
