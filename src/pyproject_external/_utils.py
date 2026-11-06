import shutil


def find_executable(name: str) -> str:
    """
    Find Unix-style executable names (no extensions) on Windows and non-Windows platforms,
    regardless `sys.platform`.
    """
    # 1. Try standard lookup
    path = shutil.which(name)
    if path:
        # On POSIX environments on Windows, ensure it's not missing .exe if a .exe sibling exists
        if not path.lower().endswith(".exe") and (exe_path := shutil.which(f"{name}.exe")):
            return exe_path
        return path

    # 2. If no match and not already ending in .exe, test .exe explicitly
    if not name.lower().endswith(".exe"):
        if exe_path := shutil.which(f"{name}.exe"):
            return exe_path

    return name
