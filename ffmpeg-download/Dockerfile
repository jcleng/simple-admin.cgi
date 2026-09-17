FROM registry.cn-hangzhou.aliyuncs.com/jcleng/linuxserver-ffmpeg:version-9.0-cli
USER root
ADD https://busybox.net/downloads/binaries/1.21.1/busybox-x86_64 /bin/busybox_new
RUN chmod +x /bin/busybox_new && mv /bin/busybox_new /bin/busybox
WORKDIR /app
COPY cgi-bin/ /app/cgi-bin/
RUN mkdir -p /app/downloads && chmod 777 /app/downloads
ENV FFMPEG_USER=admin
ENV FFMPEG_PASS=admin
ENV FFMPEG_DL_DIR=/app/downloads
ENTRYPOINT []
EXPOSE 33001
CMD ["busybox", "httpd", "-v", "-f", "-p", "33001", "-h", "."]
