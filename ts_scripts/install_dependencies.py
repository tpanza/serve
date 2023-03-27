import argparse
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from contextlib import contextmanager

from print_env_info import run_and_parse_first_match

REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.append(REPO_ROOT)

from ts_scripts.utils import check_python_version


class Common:
    def __init__(self):
        self.torch_stable_url = "https://download.pytorch.org/whl/torch_stable.html"
        self.sudo_cmd = "sudo"

    def check_for_jdk(self):
        pass

    def install_nodejs(self):
        pass

    def install_torch_packages(self, cuda_version):
        if cuda_version:
            if platform.system() == "Darwin":
                print(
                    "CUDA not supported on MacOS. Refer https://pytorch.org/ for installing from source."
                )
                sys.exit(1)
            elif cuda_version == "cu92" and platform.system() == "Windows":
                print(
                    "CUDA 9.2 not supported on Windows. Refer https://pytorch.org/ for installing from source."
                )
                sys.exit(1)
            else:
                subprocess.check_call(
                    [
                        f"{sys.executable}",
                        "-m",
                        "pip",
                        "install",
                        "-U",
                        "-r",
                        f"requirements/torch_{cuda_version}_{platform.system().lower()}.txt",
                    ]
                )
        else:
            subprocess.check_call(
                [
                    f"{sys.executable}",
                    "-m",
                    "pip",
                    "install",
                    "-U",
                    "-r",
                    f"requirements/torch_{platform.system().lower()}.txt",
                ]
            )

    def install_python_packages(self, cuda_version, requirements_file_path, nightly):
        if shutil.which("conda"):
            # conda install command should run before the pip install commands
            # as it may reinstall the packages with different versions
            subprocess.check_call(["conda", "install", "-y", "conda-build"])

        self.install_torch_packages(cuda_version)
        subprocess.check_call(
            [f"{sys.executable}", "-m", "pip", "install", "-U", "pip", "setuptools"]
        )
        # developer.txt also installs packages from common.txt
        subprocess.check_call(
            [
                f"{sys.executable}",
                "-m",
                "pip",
                "install",
                "-U",
                "-r",
                f"{requirements_file_path}",
            ]
        )
        # If conda is available install conda-build package

        # TODO: This will run 2 installations for torch but to make this cleaner we should first refactor all of our requirements.txt into just 2 files
        # And then make torch an optional dependency for the common.txt
        if nightly:
            subprocess.check_call(
                [
                    f"{sys.executable}",
                    "-m",
                    "pip",
                    "install",
                    "numpy",
                    "--pre torch[dynamo]",
                    "torchvision",
                    "torchtext",
                    "torchaudio",
                    "--force-reinstall",
                    "--extra-index-url",
                    f"https://download.pytorch.org/whl/nightly/{cuda_version}",
                ]
            )

    def install_node_packages(self):
        subprocess.check_call(
            list(
                filter(
                    None,
                    [
                        f"{self.sudo_cmd}",
                        "npm",
                        "install",
                        "-g",
                        "newman",
                        "newman-reporter-htmlextra",
                        "markdown-link-check",
                    ],
                )
            )
        )

    def install_jmeter(self):
        pass

    def install_wget(self):
        pass

    @contextmanager
    def cd(self, newdir):
        prevdir = os.getcwd()
        os.chdir(os.path.expanduser(newdir))
        try:
            yield
        finally:
            os.chdir(prevdir)


class Linux(Common):
    def __init__(self):
        super().__init__()
        # Skip 'sudo ' when the user is root
        self.sudo_cmd = "" if os.geteuid() == 0 else self.sudo_cmd

        if args.force:
            subprocess.check_call(
                list(filter(None, [f"{self.sudo_cmd}", "apt-get", "update"]))
            )

    def check_for_jdk(self):
        if not shutil.which("javac") or args.force:
            sys.exit(
                "javac not found on PATH. Please install JDK 17 appropriate for your operating system."
            )

    def install_nodejs(self):
        if not shutil.which("node") or args.force:
            with urllib.request.urlopen(
                "https://deb.nodesource.com/setup_14.x"
            ) as response, tempfile.NamedTemporaryFile() as tmp_file:
                data = response.read()
                tmp_file.write(data)
                subprocess.check_call(
                    list(filter(None, [f"{self.sudo_cmd}", "bash", tmp_file.name]))
                )
            subprocess.check_call(
                list(
                    filter(
                        None, [f"{self.sudo_cmd}", "apt-get", "install", "-y", "nodejs"]
                    )
                )
            )

    def install_wget(self):
        if not shutil.which("wget") or args.force:
            subprocess.check_call(
                list(
                    filter(
                        None, [f"{self.sudo_cmd}", "apt-get", "install", "-y", "wget"]
                    )
                )
            )

    def install_libgit2(self):
        version = "1.3.0"
        dirname = f"libgit2-{version}"
        tarballname = f"{dirname}.tar.gz"
        subprocess.check_call(
            [
                "wget",
                f"https://github.com/libgit2/libgit2/archive/refs/tags/v{version}.tar.gz",
                "-O",
                tarballname,
            ]
        )
        with tarfile.open(tarballname, "r:gz") as f:
            f.extractall()
        with self.cd(dirname):
            subprocess.check_call(["cmake", "."])
            subprocess.check_call(["make"])
            subprocess.check_call(
                list(filter(None, [f"{self.sudo_cmd}", "make", "install"]))
            )
        shutil.rmtree(dirname)
        os.remove(tarballname)


class Windows(Common):
    def __init__(self):
        super().__init__()
        self.sudo_cmd = ""

    def check_for_jdk(self):
        pass

    def install_nodejs(self):
        pass

    def install_wget(self):
        pass


class Darwin(Common):
    def __init__(self):
        super().__init__()

    def check_for_jdk(self):
        if not shutil.which("javac") or args.force:
            out = get_brew_version()
            if out == "N/A":
                sys.exit("**Error: Homebrew not installed...")
            subprocess.check_call(["brew", "install", "openjdk@17"])

    def install_nodejs(self):
        subprocess.check_call(["brew", "unlink", "node"])
        subprocess.check_call(["brew", "install", "node@14"])
        subprocess.check_call(["brew", "link", "--overwrite", "node@14"])

    def install_node_packages(self):
        subprocess.check_call(
            list(filter(None, [f"{self.sudo_cmd}", "./ts_scripts/mac_npm_deps"]))
        )

    def install_wget(self):
        if not shutil.which("wget") or args.force:
            subprocess.check_call(["brew", "install", "wget"])


def install_dependencies(cuda_version=None, nightly=False):
    os_map = {"Linux": Linux, "Windows": Windows, "Darwin": Darwin}
    system = os_map[platform.system()]()

    if args.environment == "dev":
        system.install_wget()
        system.install_nodejs()
        system.install_node_packages()

    if platform.system() == "Linux" and args.environment == "dev":
        system.install_libgit2()

    # Sequence of installation to be maintained
    system.check_for_jdk()
    requirements_file_path = "requirements/" + (
        "production.txt" if args.environment == "prod" else "developer.txt"
    )
    system.install_python_packages(cuda_version, requirements_file_path, nightly)


def get_brew_version():
    """Returns `brew --version` output."""

    return run_and_parse_first_match("brew --version", r"Homebrew (.*)")


if __name__ == "__main__":
    check_python_version()
    parser = argparse.ArgumentParser(
        description="Install various build and test dependencies of TorchServe"
    )
    parser.add_argument(
        "--cuda",
        default=None,
        choices=["cu92", "cu101", "cu102", "cu111", "cu113", "cu116", "cu117", "cu118"],
        help="CUDA version for torch",
    )
    parser.add_argument(
        "--environment",
        default="prod",
        choices=["prod", "dev"],
        help="environment(production or developer) on which dependencies will be installed",
    )

    parser.add_argument(
        "--nightly_torch",
        action="store_true",
        help="Install nightly version of torch package",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="force reinstall dependencies wget, node, java and apt-update",
    )
    args = parser.parse_args()

    install_dependencies(cuda_version=args.cuda, nightly=args.nightly_torch)
