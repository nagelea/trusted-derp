FROM docker.io/library/golang:1.27.3-bookworm@sha256:c93aa68d51e382ec1ab4caa559ae9efd7858d8e5330051671c56c1096eaccd66 AS build

ARG TAILSCALE_VERSION=v1.104.5
ARG TAILSCALE_COMMIT=73a48057aaf5f60e4f770b398e9b7af576b01dbe
ENV CGO_ENABLED=0 GOTOOLCHAIN=local GOMAXPROCS=1 GOMEMLIMIT=640MiB GOGC=50
WORKDIR /src
RUN git init . && git remote add origin https://github.com/tailscale/tailscale.git \
    && git fetch --depth=1 origin "${TAILSCALE_COMMIT}" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${TAILSCALE_COMMIT}"
RUN go mod download && go mod verify
RUN mkdir -p /out \
    && go build -p=1 -trimpath -buildvcs=true -ldflags='-s -w -buildid=' -o /out/derper ./cmd/derper \
    && go build -p=1 -trimpath -buildvcs=true -ldflags='-s -w -buildid=' -o /out/tailscaled ./cmd/tailscaled \
    && go build -p=1 -trimpath -buildvcs=true -ldflags='-s -w -buildid=' -o /out/tailscale ./cmd/tailscale \
    && go version -m /out/derper /out/tailscaled /out/tailscale > /out/buildinfo.txt \
    && go list -m -json all > /out/modules.json \
    && printf '{"upstream_version":"%s","upstream_commit":"%s","go_version":"%s"}\n' \
       "${TAILSCALE_VERSION}" "${TAILSCALE_COMMIT}" "$(go env GOVERSION)" > /out/build.json \
    && cd /out && sha256sum derper tailscaled tailscale > SHA256SUMS

FROM scratch
LABEL org.opencontainers.image.title="Auditable Tailscale DERP" \
      org.opencontainers.image.description="DERP and userspace identity binaries built together from pinned official source" \
      org.opencontainers.image.licenses="BSD-3-Clause"
COPY --from=build /out/derper /out/tailscale /out/tailscaled /usr/local/bin/
COPY --from=build /out/build.json /out/buildinfo.txt /out/modules.json /out/SHA256SUMS /usr/share/derp/
COPY --from=build /src/LICENSE /usr/share/licenses/tailscale/LICENSE
COPY --from=build /usr/local/go/LICENSE /usr/share/licenses/go/LICENSE
COPY --from=build /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
USER 65532:65532
EXPOSE 8443/tcp 13478/udp
ENTRYPOINT ["/usr/local/bin/derper"]
CMD ["--help"]
