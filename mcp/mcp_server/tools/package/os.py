from __future__ import annotations
from typing import List, Optional
import sys
from PIL import Image
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps
import uno

import fnmatch
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pyautogui
import ast
import operator

class UnifiedTools:

    @staticmethod
    def open_shell():
        pyautogui.hotkey('ctrl', 'alt', 't')
    # ──────────────────────────────────────────────────────────────────────
    # 0) 通用 / 内部小工具
    # ──────────────────────────────────────────────────────────────────────

    class _Shell:
        """SystemVolumeTools 原来的安全调用器"""
        @staticmethod
        def run(cmd: str) -> Tuple[int, str, str]:
            proc = subprocess.Popen(
                shlex.split(cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            out, err = proc.communicate()
            return proc.returncode, out.strip(), err.strip()

    # ──────────────────────────────────────────────────────────────────────
    # TerminalSizeTools  ---------------------------------------------------
    # ──────────────────────────────────────────────────────────────────────
    @staticmethod
    def _ts_run(cmd: str) -> Tuple[int, str, str]:
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        out, err = proc.communicate()
        return proc.returncode, out.strip(), err.strip()

    @classmethod
    def _ts_get_default_profile_uuid(cls) -> str:
        rc, out, _ = cls._ts_run(
            "gsettings get org.gnome.Terminal.ProfilesList default"
        )
        if rc == 0 and out.startswith("'") and out.endswith("'"):
            return out.strip("'")
        return ""

    # ---- public ----------------------------------------------------------
    @classmethod
    def set_default_terminal_size(cls, columns: int, rows: int) -> str:
        if columns <= 0 or rows <= 0:
            return "❌  Columns / rows must be positive integers."
        if cls._ts_run("command -v gsettings")[0] != 0:
            return "❌  gsettings not found in PATH."

        profile_id = cls._ts_get_default_profile_uuid()
        if not profile_id:
            return "❌  Could not detect default GNOME-Terminal profile UUID."

        schema = (
            f"org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/"
            f"legacy/profiles:/:{profile_id}/"
        )
        for cmd in (
            f"gsettings set '{schema}' default-size-columns {columns}",
            f"gsettings set '{schema}' default-size-rows    {rows}",
        ):
            rc, _, err = cls._ts_run(cmd)
            if rc != 0:
                return f"❌  Failed while running: {cmd}\n{err}"

        return (
            f"✅  Persisted default GNOME-Terminal size: {columns}×{rows} "
            f"(profile {profile_id})."
        )

    # ──────────────────────────────────────────────────────────────────────
    # SystemVolumeTools  ---------------------------------------------------
    # ──────────────────────────────────────────────────────────────────────
    @staticmethod
    def _sv_detect_default_sink() -> Optional[str]:
        rc, out, _ = UnifiedTools._Shell.run("pactl info")
        if rc != 0:
            return None
        for line in out.splitlines():
            if line.lower().startswith("default sink:"):
                sink = line.split(":", 1)[1].strip()
                return (
                    sink
                    if sink and sink != "auto_null" and sink.lower() != "n/a"
                    else None
                )
        return None

    @classmethod
    def get_volume(cls) -> Dict[str, Any]:

        shell_script = '''
DEFAULT_SINK=$(pactl info | awk -F': ' '/Default Sink:/ {print $2}')
CURRENT_VOL=$(pactl get-sink-volume "$DEFAULT_SINK" | head -n1 | awk -F'/' '{print $2}' | xargs)
echo "$CURRENT_VOL"'''.strip()
        try:
            result = subprocess.run(
                shell_script, shell=True, capture_output=True, text=True)
            success = True
            err = None
            stdout = result.stdout
        except:
            err = "subprocess Err"
            stdout = None
            success = False

        percent = None
        if success:
            try:
                percent = int(result.stdout.strip().rstrip("%"))
            except Exception:
                percent = None
                success = False
                err = f"Unable to parse pactl output: {stdout}"
        return {
            "success": success,
            "volume_percent": percent,
            "stdout": stdout,
            "stderr": err,
        }

    @classmethod
    def set_volume(cls, percent: int) -> Dict[str, Any]:

        percent = max(0, min(percent, 100))
        shell_script = '''DEFAULT_SINK=$(pactl info | awk -F': ' '/Default Sink:/ {print $2}')''' + f'''
pactl set-sink-volume "$DEFAULT_SINK" {percent}%
if [ $? -ne 0 ]; then
  echo "Failed to set volume."
  exit 2
else
  echo "Command sent successfully."
fi'''
        try:
            result = subprocess.run(
                shell_script, shell=True, capture_output=True, text=True)
        except:
            result = None

        success = False
        if result.stdout == "Command sent successfully.\n":
            success = True
        info = cls.get_volume() if success else {}
        return {
            "success": success and info.get("success", False),
            "volume_percent": info.get("volume_percent"),
            "stdout": result.stdout,
        }

    # ──────────────────────────────────────────────────────────────────────
    # GnomeAccessibilityTools  --------------------------------------------
    # ──────────────────────────────────────────────────────────────────────
    _GA_SCHEMA = "org.gnome.desktop.interface"
    _GA_KEY = "text-scaling-factor"

    @classmethod
    def _ga_run(cls, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["gsettings", *args], capture_output=True, text=True, check=True
        )

    @staticmethod
    def _ga_parse_float(value: str) -> float:
        return float(value.strip())

    @classmethod
    def get_text_scale(cls) -> float:
        result = cls._ga_run("get", cls._GA_SCHEMA, cls._GA_KEY)
        return cls._ga_parse_float(result.stdout)

    @classmethod
    def set_text_scale(cls, scale: float) -> None:
        if not (0.5 <= scale <= 3.0):
            raise ValueError("scale should be between 0.5 and 3.0")
        subprocess.run(["which", "gsettings"],
                       check=True, stdout=subprocess.PIPE)
        cls._ga_run("set", cls._GA_SCHEMA, cls._GA_KEY, str(scale))
        new_val = cls.get_text_scale()
        if abs(new_val - scale) > 1e-3:
            raise RuntimeError(
                f"Tried to set text scale to {scale}, but system reports {new_val}"
            )

    @classmethod
    def change_text_scale(cls, new_scale: float) -> float:
        old = cls.get_text_scale()
        cls.set_text_scale(new_scale)
        return old

    # ──────────────────────────────────────────────────────────────────────
    # FileTools  -----------------------------------------------------------
    # ──────────────────────────────────────────────────────────────────────
    @classmethod
    def copy_matching_files_with_hierarchy(
        cls,
        root_dir: str = ".",
        dest_dir: str = "fails",
        pattern: str = "*failed.ipynb",
        dry_run: bool = False,
    ) -> List[Tuple[str, str]]:
        copied: list[tuple[str, str]] = []
        root_dir = os.path.abspath(os.path.expanduser(root_dir))
        dest_dir_abs = os.path.abspath(os.path.join(root_dir, dest_dir))

        for dirpath, dirnames, filenames in os.walk(root_dir):
            dirnames[:] = [
                d
                for d in dirnames
                if os.path.abspath(os.path.join(dirpath, d)) != dest_dir_abs
            ]
            for filename in filenames:
                if fnmatch.fnmatch(filename, pattern):
                    src_path = os.path.join(dirpath, filename)
                    rel_path = os.path.relpath(src_path, root_dir)
                    dst_path = os.path.join(dest_dir_abs, rel_path)
                    copied.append((src_path, dst_path))
                    if dry_run:
                        continue
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    shutil.copy2(src_path, dst_path)
        return copied

    # -- copy_file_to_directories -----------------------------------------
    file_ret: str = ""

    @classmethod
    def print_result(cls) -> None:
        print(cls.file_ret)

    # ──────────────────────────────────────────────────────────────────────
    # TrashTools  ----------------------------------------------------------
    # ──────────────────────────────────────────────────────────────────────
    _TRASH_FILES = Path.home() / ".local/share/Trash/files"
    _TRASH_INFO = Path.home() / ".local/share/Trash/info"

    @classmethod
    def _trash_ensure(cls) -> None:
        if not cls._TRASH_FILES.is_dir() or not cls._TRASH_INFO.is_dir():
            raise FileNotFoundError("Trash directory not found – expected "
                                    f"{cls._TRASH_FILES} and {cls._TRASH_INFO}")

    @classmethod
    def _trash_info_path(cls, filename: str) -> Path:
        return cls._TRASH_INFO / f"{filename}.trashinfo"

    @classmethod
    def get_trash_directory(cls) -> str:
        """
        Return the absolute path to the user Trash ‘files’ directory, e.g.
        /home/USER/.local/share/Trash/files
        """
        return str(cls._TRASH_FILES.resolve())

    # ---------- 通用文件搜索（替代原 search_files） --------------- #
    @classmethod
    def search_files(cls,
                     keyword: str,
                     root_dir: str = ".") -> List[str]:
        """
        Recursively search *root_dir* for files whose **basename**
        contains *keyword* (case-insensitive).

        Returns a list of absolute paths.
        """
        matches: List[str] = []
        root = Path(root_dir).expanduser().resolve()
        keyword = keyword.lower()

        for p in root.rglob("*"):
            if p.is_file() and keyword in p.name.lower():
                matches.append(str(p))

        return matches

    @classmethod
    def restore_file(cls, file_name: str) -> str:
        """
        Restore *file_name* from the user Trash back to its original path.

        Parameters
        ----------
        file_name : str
            Exact basename as shown in ~/.local/share/Trash/files .
            Example:  "holiday_poster.png"

        Returns
        -------
        str
            Absolute path where the file was restored.

        Raises
        ------
        FileNotFoundError – if the given file does not exist in Trash
        RuntimeError      – if .trashinfo is missing or move fails
        """
        trash_dir = Path(cls.get_trash_directory())
        info_dir = cls._TRASH_INFO
        if str(trash_dir) in file_name:
            file_name = file_name.split(str(trash_dir) + '/')[-1]
        elif str(info_dir) in file_name:
            file_name = file_name.split(str(info_dir) + '/')[-1]
        chosen_path = trash_dir / file_name
        info_path = info_dir / f"{file_name}.trashinfo"

        # 1) 目标是否存在
        if not chosen_path.is_file():
            raise FileNotFoundError(f"{file_name!r} not found in Trash")

        # 2) 解析原始路径
        orig_path: Optional[str] = None
        if info_path.is_file():
            with info_path.open(encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    if line.startswith("Path="):
                        orig_path = line[len("Path="):].strip()
                        break
        if not orig_path:
            raise RuntimeError(
                f"Could not read original path from {info_path}")

        orig_path = os.path.expanduser(orig_path)
        Path(os.path.dirname(orig_path)).mkdir(parents=True, exist_ok=True)

        # 3) 执行恢复
        shutil.move(str(chosen_path), orig_path)
        info_path.unlink(missing_ok=True)
        return orig_path

    # ──────────────────────────────────────────────────────────────────────
    # UbuntuPackageTools  --------------------------------------------------
    # ──────────────────────────────────────────────────────────────────────
    @staticmethod
    def _upt_run(cmd: List[str]) -> Tuple[bool, List[str]]:
        completed = subprocess.run(
            cmd, capture_output=True, text=True, check=False)
        ok = completed.returncode == 0
        out = (completed.stdout or "").splitlines()
        err = (completed.stderr or "").splitlines()
        return ok, [f"$ {' '.join(cmd)}"] + out + err

    # ──────────────────────────────────────────────────────────────────────
    # ScreenLockTools  -----------------------------------------------------
    # ──────────────────────────────────────────────────────────────────────
    _SL_SCHEMA_SESSION = "org.gnome.desktop.session"
    _SL_SCHEMA_SAVER = "org.gnome.desktop.screensaver"

    @staticmethod
    def _sl_run(cmd: str) -> str:
        result = subprocess.run(cmd.split(), capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return result.stdout.strip()

    @staticmethod
    def _sl_ensure_gsettings() -> None:
        if shutil.which("gsettings") is None:
            raise RuntimeError(
                "`gsettings` command not found. Install it via "
                "`sudo apt install dconf-cli`."
            )

    @classmethod
    def configure_auto_lock(
        cls,
        idle_delay_seconds: int,
        lock_delay_seconds: int = 0,
        enable_lock: bool = True,
    ) -> Dict[str, Any]:
        if idle_delay_seconds < 0 or lock_delay_seconds < 0:
            raise ValueError("Delays must be non-negative integers")
        cls._sl_ensure_gsettings()
        cls._sl_run(
            f"gsettings set {cls._SL_SCHEMA_SESSION} idle-delay {idle_delay_seconds}"
        )
        cls._sl_run(
            f"gsettings set {cls._SL_SCHEMA_SAVER} lock-enabled "
            f"{'true' if enable_lock else 'false'}"
        )
        cls._sl_run(
            f"gsettings set {cls._SL_SCHEMA_SAVER} lock-delay {lock_delay_seconds}"
        )
        return cls.get_current_settings()

    # ──────────────────────────────────────────────────────────────────────
    # TimeZoneTools  -------------------------------------------------------
    # ──────────────────────────────────────────────────────────────────────
    @staticmethod
    def _tz_run(cmd: str, sudo_password: Optional[str] = None) -> Tuple[int, str, str]:
        if sudo_password:
            cmd = f"echo {shlex.quote(sudo_password)} | sudo -S {cmd}"
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        out, err = proc.communicate()
        return proc.returncode, out.strip(), err.strip()

    # ──────────────────────────────────────────────────────────────────────
    # FsTools  -------------------------------------------------------------
    # ──────────────────────────────────────────────────────────────────────
    fs_ret: str = ""

    @classmethod
    def rename_directory(
        cls, old_path: str, new_path: str, create_intermediate: bool = False
    ) -> bool:
        try:
            old_dir = Path(os.path.expanduser(old_path)).resolve()
            new_dir = Path(os.path.expanduser(new_path)).resolve()
            if not old_dir.exists():
                cls.fs_ret = f"Error: source directory not found: {old_dir}"
                return False
            if not old_dir.is_dir():
                cls.fs_ret = f"Error: source path is not a directory: {old_dir}"
                return False
            if new_dir.exists():
                cls.fs_ret = f"Error: target already exists: {new_dir}"
                return False
            if create_intermediate:
                new_dir.parent.mkdir(parents=True, exist_ok=True)
            elif not new_dir.parent.exists():
                cls.fs_ret = (
                    f"Error: target parent directory does not exist: {new_dir.parent}"
                )
                return False
            shutil.move(str(old_dir), str(new_dir))
            cls.fs_ret = (
                f"Success: '{old_dir.name}' renamed to '{new_dir.name}'.\n"
                f"Full path: {new_dir}"
            )
            return True
        except Exception as exc:
            cls.fs_ret = f"Unhandled exception: {exc}"
            return False

    # ──────────────────────────────────────────────────────────────────────
    # NotificationTools  ---------------------------------------------------
    # ──────────────────────────────────────────────────────────────────────
    @staticmethod
    def _nt_run_cmd(cmd: List[str]) -> Tuple[bool, str]:
        try:
            res = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True
            )
            return True, res.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, e.output.strip()

    @staticmethod
    def _nt_gsettings_available() -> bool:
        return shutil.which("gsettings") is not None

    @classmethod
    def set_do_not_disturb(cls, enable: bool) -> bool:
        if not cls._nt_gsettings_available():
            print("Error: `gsettings` not found.")
            return False
        value = "false" if enable else "true"   # GNOME 逻辑
        ok, out = cls._nt_run_cmd(
            ["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", value]
        )
        if not ok:
            print("Failed to change notification setting:", out)
        return ok

    @classmethod
    def get_do_not_disturb_status(cls) -> Optional[bool]:
        if not cls._nt_gsettings_available():
            print("Error: `gsettings` not found.")
            return None
        ok, out = cls._nt_run_cmd(
            ["gsettings", "get", "org.gnome.desktop.notifications", "show-banners"]
        )
        if not ok:
            print("Failed to read notification setting:", out)
            return None
        out = out.strip().lower()
        if out == "false":
            return True
        if out == "true":
            return False
        return None

    @staticmethod
    def remove_image_background(image_path, output_path):
        """
        Remove background from an image. 
        Automatically installs 'rembg' if not found.
        """
        try:
            # Try import, auto-install if missing
            # need install onnxruntime
            try:
                from rembg import remove
            except ImportError:
                print("Module 'rembg' not found. Installing now...")
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "rembg"])
                from rembg import remove  # Re-import after install

            try:
                import onnxruntime
            except ImportError:
                print("Module 'onnxruntime' not found. Installing now...")
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "onnxruntime"])
                import onnxruntime

            if not os.path.exists(image_path):
                return f"Error: image_path '{image_path}' does not exist."

            # Ensure output folder exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Perform background removal
            with open(image_path, 'rb') as inp:
                result = remove(inp.read())

            with open(output_path, 'wb') as out:
                out.write(result)

            return f"Background removed successfully → {output_path}"

        except Exception as e:
            return f"Error removing background: {e}"

    @staticmethod
    def convert_image_format(image_path, output_format, output_path):
        try:
            img = Image.open(image_path)
            if output_format.lower() == "jpg" and img.mode in ("RGBA", "LA"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                background.save(output_path, output_format.upper())
            else:
                img.save(output_path, format=output_format.upper())
            return "Image converted"
        except Exception as e:
            return f"Error converting image: {e}"

    @staticmethod
    def git_operation(repo_path, operation, arguments=None):
        try:
            cmd = ["git", operation] + (arguments or [])
            subprocess.run(
                cmd, cwd=repo_path if repo_path else None, check=True)
            return f"Git {operation} executed"
        except Exception as e:
            return f"Error running git {operation}: {e}"

    @staticmethod
    def git_set_user_info(username, email, is_global=True, repo_path=None):
        """
        Set git username and email globally or for a specific repository.

        Args:
            username (str): Git username
            email (str): Git email
            is_global (bool): True for global config, False for repo-only
            repo_path (str, optional): Path to repository (only used if is_global=False)
        """
        try:
            # Check if git is installed
            if shutil.which("git") is None:
                return "Error: Git is not installed or not found in PATH."

            if is_global:
                subprocess.run(["git", "config", "--global",
                               "user.name", username], check=True)
                subprocess.run(["git", "config", "--global",
                               "user.email", email], check=True)
                return f"Git global user set: {username} <{email}>"
            else:
                target_path = repo_path if repo_path else "."
                subprocess.run(["git", "config", "user.name",
                               username], cwd=target_path, check=True)
                subprocess.run(["git", "config", "user.email",
                               email], cwd=target_path, check=True)
                return f"Git local user set for repo at {target_path}: {username} <{email}>"
        except subprocess.CalledProcessError as e:
            return f"Error setting git user info: {e}"
        except Exception as e:
            return f"Unexpected error: {e}"

    @staticmethod
    def calculator(expression: str):
        """
        Safely evaluate a simple Python arithmetic expression.

        Args:
            expression (str): Python arithmetic expression
        Returns:
            str: Result or error message
        """

        # 允许的 AST 节点类型
        allowed_nodes = (
            ast.Expression, ast.BinOp, ast.UnaryOp,
            ast.Num, ast.Constant, 
            ast.Add, ast.Sub, ast.Mult, ast.Div,
            ast.Pow, ast.Mod, ast.FloorDiv,
            ast.USub, ast.UAdd, ast.Load,
            ast.Tuple, ast.List
        )

        def _is_safe(node):
            """递归检查 AST 节点"""
            if not isinstance(node, allowed_nodes):
                return False
            for child in ast.iter_child_nodes(node):
                if not _is_safe(child):
                    return False
            return True

        try:
            # 解析 AST
            parsed = ast.parse(expression, mode="eval")

            # 检查 AST 是否安全
            if not _is_safe(parsed):
                return "Error: Expression contains unsafe or unsupported operations."

            # 安全执行表达式
            result = eval(compile(parsed, filename="<calc>", mode="eval"), {"__builtins__": {}})
            return str(result)

        except Exception as e:
            return f"Error evaluating expression: {e}"

    @staticmethod
    def ffmpeg_video_to_gif(video_path, start_time, duration, output_path):
        try:
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start_time),
                "-t", str(duration),
                "-i", video_path,
                "-vf", "fps=10,scale=480:-1:flags=lanczos",
                output_path
            ]
            subprocess.run(cmd, check=True)
            return "GIF created"
        except Exception as e:
            return f"Error creating GIF: {e}"
