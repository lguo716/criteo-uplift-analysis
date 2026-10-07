import os
import sys

from nbclient import NotebookClient
from jupyter_client import KernelManager
import nbformat

from .config import ROOT


def main():
    for name in ["runtime", "config", "ipython"]:
        (ROOT / ".jupyter" / name).mkdir(parents=True, exist_ok=True)
    os.environ["JUPYTER_RUNTIME_DIR"] = str(ROOT / ".jupyter/runtime")
    os.environ["JUPYTER_CONFIG_DIR"] = str(ROOT / ".jupyter/config")
    os.environ["IPYTHONDIR"] = str(ROOT / ".jupyter/ipython")
    for path in sorted((ROOT / "notebooks").glob("*.ipynb")):
        notebook = nbformat.read(path, as_version=4)
        manager = KernelManager(kernel_name="python3")
        manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
        client = NotebookClient(notebook, km=manager, timeout=180, resources={"metadata": {"path": str(ROOT)}})
        client.execute()
        nbformat.write(notebook, path)
        print("Executed:", path.name)


if __name__ == "__main__":
    main()
