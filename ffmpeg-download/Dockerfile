FROM registry.cn-hangzhou.aliyuncs.com/jcleng/library-alpine:3.20.1
USER root
COPY --from=registry.cn-hangzhou.aliyuncs.com/jcleng/library-docker:24.0.9-cli /usr/local/bin/docker /usr/local/bin/docker
ADD https://busybox.net/downloads/binaries/1.21.1/busybox-x86_64 /bin/busybox_new
RUN chmod +x /bin/busybox_new && mv /bin/busybox_new /bin/busybox
ADD https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffmpeg-linux-x64 /usr/local/bin/ffmpeg
ADD https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffprobe-linux-x64 /usr/local/bin/ffprobe
RUN chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe
WORKDIR /app
COPY cgi-bin/ /app/cgi-bin/
RUN mkdir -p /app/downloads && chmod 777 /app/downloads
ENV FFMPEG_USER=admin
ENV FFMPEG_PASS=admin
ENV FFMPEG_DL_DIR=/app/downloads
EXPOSE 33001
CMD ["busybox", "httpd", "-v", "-f", "-p", "33001", "-h", "."]
