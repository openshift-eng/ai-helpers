# Cross-Compiling for RHCOS

RHCOS worker nodes run `linux/amd64`. If you are building from an arm64 Mac (Apple Silicon), you need to cross-compile using Docker with QEMU emulation.

## Why Not Build on the Node?

RHCOS is an immutable OS. It has no package manager (`dnf`/`yum`), no development headers, and no Go toolchain. Building must happen off-cluster.

## Why Not Build a Static Binary?

RHCOS ships dynamically-linked binaries. The target binary must link against the same shared libraries (same sonames) as the RPM-installed version on RHCOS. A statically-linked binary might work but diverges from the production configuration and may miss features gated behind dynamic library detection (e.g., SELinux, seccomp, gpgme).

## Build Procedure

### 1. Determine the Go Version

Check `go.mod` in the source directory:

```bash
head -3 go.mod
```

Use the matching `golang:<version>-bookworm` Docker image.

### 2. Determine Library Dependencies

SSH into the target node and check what the existing binary links against:

```bash
node_ssh "ldd \$(which <binary>)"
```

The cross-compiled binary must link against the same sonames.

### 3. Create a Dockerfile

Use a base image with matching libraries. Check the node's base OS first (`node_ssh "cat /etc/os-release; ldd --version | head -1"`, with `node_ssh` from [ssh-bastion.md](ssh-bastion.md)): the RHEL major version behind RHCOS changes between OCP releases. The build image's glibc must not be newer than the node's. For RHEL 9 based RHCOS, Debian Bookworm works; a UBI or CentOS Stream image of the same RHEL major version is the safest choice. `fedora:latest` usually has a newer glibc than the node.

The binary-specific reference (e.g., [crio.md](crio.md)) lists the exact packages and build tags needed.

```dockerfile
FROM --platform=linux/amd64 golang:<version>-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    <packages from binary-specific reference> \
    pkg-config make git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build/<project>
COPY . .

RUN make <target> && ldd <output-binary>
```

### 4. Build

```bash
docker build --platform linux/amd64 -f Dockerfile.cross -t <name>-cross .
```

This uses QEMU emulation on arm64 Mac. Expect builds to take 2-5x longer than native.

### 5. Extract the Binary

```bash
docker create --platform linux/amd64 --name extract <name>-cross
mkdir -p bin
docker cp extract:/build/<project>/<binary-path> ./bin/<binary-name>
docker rm extract
```

### 6. Verify Architecture

```bash
file ./bin/<binary-name>
# Should show: ELF 64-bit LSB executable, x86-64
```

## Go Cross-Compile Settings

For Go binaries (CRI-O, conmon-rs components):

```bash
GOOS=linux GOARCH=amd64 CGO_ENABLED=1
```

`CGO_ENABLED=1` is required because these binaries link against C libraries (libseccomp, libgpgme, etc.). The Docker container provides the correct C toolchain for the target platform.

## Rust Cross-Compile (conmon-rs)

conmon-rs is written in Rust. Cross-compile for `x86_64-unknown-linux-gnu`:

```bash
# In the Docker container (linux/amd64, so the host target is already
# x86_64-unknown-linux-gnu and no extra rustup target is needed)
cargo build --release
```

Use a RHEL-compatible container of the node's RHEL major version, so the system libraries match. Some `-devel` packages come from the CRB repository (`dnf config-manager --set-enabled crb`) or EPEL. The Dockerfile should install:

```dockerfile
# Match the node's RHEL major version (see "glibc compatibility" above), for
# example CentOS Stream 9 for RHEL 9 based RHCOS. Not fedora:latest, whose
# glibc is newer than the node's.
FROM --platform=linux/amd64 quay.io/centos/centos:stream<rhel-major>

RUN dnf install -y \
    rust cargo \
    glib2-devel libseccomp-devel systemd-devel \
    capnproto capnp-devel \
    pkg-config make git \
    && dnf clean all

WORKDIR /build/conmon-rs
COPY . .

RUN cargo build --release && ldd target/release/conmonrs
```

## C Cross-Compile (crun)

crun uses autotools. Build in a matching container:

```dockerfile
# Match the node's RHEL major version (see "glibc compatibility" above), for
# example CentOS Stream 9 for RHEL 9 based RHCOS. Not fedora:latest, whose
# glibc is newer than the node's.
FROM --platform=linux/amd64 quay.io/centos/centos:stream<rhel-major>

RUN dnf install -y \
    gcc automake autoconf libtool \
    libcap-devel systemd-devel \
    yajl-devel libseccomp-devel \
    python3 git \
    && dnf clean all

WORKDIR /build/crun
COPY . .

RUN ./autogen.sh && ./configure && make
RUN ldd crun
```

## Verifying the Binary

After extraction, verify in a matching container:

```bash
# Run ldd inside a matching container to confirm library compatibility
docker run --platform linux/amd64 --rm -v $(pwd)/bin:/check debian:bookworm \
  ldd /check/<binary-name>
```

All libraries must resolve. If any show `not found`, the binary was built against incompatible library versions.

## Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ldd` shows `not found` | Wrong base image or missing -dev package | Check sonames on target node, use matching base image |
| `GLIBC_x.xx not found` | glibc version mismatch | Use older base image (match the RHEL major version of the node; bookworm is usually safe for RHEL 9 based RHCOS) |
| Binary runs but features missing | Wrong build tags | Check binary-specific reference for required tags |
| Exec format error on node | Wrong architecture | Verify `file` output shows `x86-64` |
| Build extremely slow | QEMU emulation on arm64 Mac | Expected, 2-5x slower than native |
