FROM registry.cn-hangzhou.aliyuncs.com/jcleng/library-alpine:3.20.1
USER root
COPY --from=registry.cn-hangzhou.aliyuncs.com/jcleng/library-docker:24.0.9-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=registry.cn-hangzhou.aliyuncs.com/jcleng/library-docker:24.0.9-cli /usr/local/bin/docker-compose /usr/local/bin/docker-compose
ADD https://busybox.net/downloads/binaries/1.21.1/busybox-x86_64 /bin/busybox_new
RUN chmod +x /bin/busybox_new && mv /bin/busybox_new /bin/busybox
