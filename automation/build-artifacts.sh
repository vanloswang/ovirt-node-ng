# vim: et sts=2 sw=2

set -ex

export ARTIFACTSDIR=$PWD/exported-artifacts

export PATH=$PATH:/sbin:/usr/sbin
export TMPDIR=$PWD/tmp
export LIBGUESTFS_BACKEND=direct

export BRANCH=master

# Only set a proxy if we can reach it
export http_proxy=http://proxy.phx.ovirt.org:3128
if curl -m 1 -o /dev/null --fail --proxy $http_proxy "http://www.ovirt.org"; then
  export CURLOPTS="-x $http_proxy"
  export LMCOPTS="--proxy $http_proxy"
fi

prepare() {
  mknod /dev/kvm c 10 232 || :
  virt-host-validate || :

  mkdir "$TMPDIR"
  mkdir "$ARTIFACTSDIR"
}

build() {
  # Build the squashfs for a later export
  ./autogen.sh --with-tmpdir=/var/tmp

  # Add this jenkins job as a repository
  cat <<EOF >> data/ovirt-node-ng-image.ks

%post
cat > /etc/yum.repos.d/ovirt-node.repo <<__EOR__
[ovirt-node-ng-${BRANCH}]
name=oVirt Node Next (${BRANCH} Nightly)
baseurl=http://jenkins.ovirt.org/job/ovirt-node-ng_${BRANCH}_build-artifacts-fc22-x86_64/lastSuccessfulBuild/artifact/exported-artifacts/
enabled=1
gpgcheck=0
metadata_expire=60
skip_if_unavailable=1
keepcache=0
__EOR__
%end
EOF

  sudo -E make squashfs
  sudo -E make product.img rpm
  sudo -E make offline-installation-iso

  sudo ln -fv \
    *manifest* \
    tmp.repos/SRPMS/*.rpm \
    tmp.repos/RPMS/noarch/*.rpm \
    ovirt-node*.squashfs.img \
    product.img \
    ovirt-node*.iso \
    data/ovirt-node*.ks \
    *.log \
    "$ARTIFACTSDIR/"
}

check() {
  # script is used, because virt-install requires a tty
  # (which ain't available in Jenkins)
  sudo -E script -efqc "make installed-squashfs"
  sudo -E script check
  sudo ln -fv \
    *.img \
    tests/*.xml \
    "$ARTIFACTSDIR/"

  ls -shal "$ARTIFACTSDIR/" || :
}

repofy_and_checksum() {
  pushd "$ARTIFACTSDIR/"
  createrepo .
  sha256sum * > CHECKSUMS.sha256 || :

  # Helper to redirect to latest installation iso
  INSTALLATIONISO=$(ls *.iso)
  echo "<html><head><meta http-equiv='refresh' content='0; url=\"$INSTALLATIONISO\"' /></head></html>" > latest-installation-iso.html
  popd
}

prepare
build
check
repofy_and_checksum
