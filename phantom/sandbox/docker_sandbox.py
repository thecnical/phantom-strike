"""
PhantomStrike DockerSandbox — Isolated execution of offensive tools inside a
kalilinux/kali-rolling container.

Provides:
  - is_available()      — check Docker daemon availability
  - start()             — pull image if needed, start container with /phantom-data volume
  - stop()              — stop and remove the running container
  - run_command()       — exec arbitrary command inside the container
  - run_nmap()          — thin wrapper: nmap scan
  - run_sqlmap()        — thin wrapper: sqlmap web scan
  - run_hydra()         — thin wrapper: hydra brute-force
  - run_john()          — thin wrapper: john the ripper
  - run_hashcat()       — thin wrapper: hashcat
  - run_metasploit()    — thin wrapper: msfconsole with resource script
  - run_impacket()      — thin wrapper: impacket tool
  - upload_file()       — copy local file into container via Docker SDK
  - download_file()     — copy file from container to local path via Docker SDK

All methods return ``{"success": False, "error": "Docker not available ..."}``
when Docker is not installed or the daemon is not running.  No unhandled
exceptions are ever propagated from any public method.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import subprocess
import tarfile
from typing import Dict, Optional

logger = logging.getLogger("phantom.sandbox.docker")

# ---------------------------------------------------------------------------
# Error message constants
# ---------------------------------------------------------------------------
_DOCKER_UNAVAILABLE_ERROR = (
    "Docker not available — install Docker for sandboxed execution"
)
_CONTAINER_NOT_RUNNING_ERROR = (
    "Container is not running — call start() first"
)


class DockerSandbox:
    """
    Runs offensive tools inside a ``kalilinux/kali-rolling`` Docker container.

    The container mounts a shared volume at ``/phantom-data`` so that files
    can be exchanged between the host and the container via ``upload_file()``
    and ``download_file()``.

    When Docker is unavailable every public method returns a dict with
    ``success=False`` and a descriptive ``error`` key — no exceptions are
    raised.
    """

    image: str = "kalilinux/kali-rolling"

    def __init__(self, image: str = "kalilinux/kali-rolling") -> None:
        self.image = image
        self._container = None          # docker.models.containers.Container
        self._docker_client = None      # docker.DockerClient
        self._docker_available: Optional[bool] = None  # cached availability flag

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self):
        """Return a cached docker.DockerClient, or None if unavailable."""
        if self._docker_client is not None:
            return self._docker_client
        try:
            import docker  # type: ignore
            client = docker.from_env()
            client.ping()
            self._docker_client = client
            return client
        except Exception:
            return None

    def _unavailable_result(self) -> Dict:
        """Standard failure dict returned when Docker is not available."""
        return {"success": False, "error": _DOCKER_UNAVAILABLE_ERROR}

    def _container_not_running_result(self) -> Dict:
        """Standard failure dict returned when the container is not started."""
        return {"success": False, "error": _CONTAINER_NOT_RUNNING_ERROR}

    # ------------------------------------------------------------------
    # Availability and lifecycle
    # ------------------------------------------------------------------

    async def is_available(self) -> bool:
        """
        Check whether the Docker daemon is reachable.

        Uses ``docker info`` via subprocess as a lightweight probe so that
        the docker SDK is not required for the availability check.

        Returns
        -------
        bool
            ``True`` if Docker is installed and the daemon is running,
            ``False`` otherwise.
        """
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    ["docker", "info"],
                    capture_output=True,
                    timeout=10,
                ),
            )
            available = result.returncode == 0
            self._docker_available = available
            return available
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            self._docker_available = False
            return False
        except Exception as exc:
            logger.warning("Unexpected error checking Docker availability: %s", exc)
            self._docker_available = False
            return False

    async def start(self) -> bool:
        """
        Pull the Kali image if needed and start the sandbox container.

        The container is started with:
        - ``/phantom-data`` volume mount (host temp dir ↔ container)
        - ``network_mode="host"`` so tools can reach targets directly
        - ``detach=True`` so the call returns immediately
        - ``tty=True`` / ``stdin_open=True`` to keep the container alive

        Returns
        -------
        bool
            ``True`` on success, ``False`` if Docker is unavailable or an
            error occurs.
        """
        if not await self.is_available():
            logger.warning("Docker not available — cannot start sandbox container")
            return False

        client = self._get_client()
        if client is None:
            return False

        try:
            # Ensure the image is present (pull if missing)
            try:
                client.images.get(self.image)
                logger.debug("Image %s already present", self.image)
            except Exception:
                logger.info("Pulling image %s …", self.image)
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: client.images.pull(self.image)
                )

            # Create a host directory for the shared volume
            host_data_dir = os.path.expanduser("~/.phantom-strike/sandbox-data")
            os.makedirs(host_data_dir, exist_ok=True)

            # Start the container
            self._container = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.containers.run(
                    self.image,
                    command="tail -f /dev/null",  # keep alive
                    detach=True,
                    tty=True,
                    stdin_open=True,
                    network_mode="host",
                    volumes={
                        host_data_dir: {
                            "bind": "/phantom-data",
                            "mode": "rw",
                        }
                    },
                    name="phantom-sandbox",
                    remove=False,
                ),
            )
            logger.info(
                "Sandbox container started: %s (%s)",
                self._container.short_id,
                self.image,
            )
            return True

        except Exception as exc:
            logger.error("Failed to start sandbox container: %s", exc)
            self._container = None
            return False

    async def stop(self) -> None:
        """
        Stop and remove the running sandbox container.

        Safe to call even if the container is not running — errors are
        logged but not raised.
        """
        if self._container is None:
            return

        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._container.stop(timeout=10),
            )
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._container.remove(force=True),
            )
            logger.info("Sandbox container stopped and removed")
        except Exception as exc:
            logger.warning("Error stopping sandbox container: %s", exc)
        finally:
            self._container = None

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    async def run_command(self, cmd: str, timeout: int = 60) -> Dict:
        """
        Execute *cmd* inside the running container.

        Parameters
        ----------
        cmd:
            Shell command string to execute inside the container.
        timeout:
            Maximum seconds to wait for the command to complete.

        Returns
        -------
        dict
            ``{"success": bool, "stdout": str, "stderr": str}``
            or ``{"success": False, "error": str}`` when Docker / container
            is unavailable.
        """
        if not await self.is_available():
            return self._unavailable_result()

        if self._container is None:
            return self._container_not_running_result()

        try:
            exit_code, output = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._container.exec_run(
                    cmd=["sh", "-c", cmd],
                    stdout=True,
                    stderr=True,
                    demux=True,
                    tty=False,
                ),
            )

            stdout_bytes, stderr_bytes = output if output else (b"", b"")
            stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")
            stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")

            return {
                "success": exit_code == 0,
                "stdout": stdout,
                "stderr": stderr,
            }

        except Exception as exc:
            logger.error("Error executing command in container: %s", exc)
            return {"success": False, "stdout": "", "stderr": str(exc)}

    # ------------------------------------------------------------------
    # Tool wrappers
    # ------------------------------------------------------------------

    async def run_nmap(self, target: str, flags: str = "-sV -sC") -> Dict:
        """
        Run nmap against *target* inside the sandbox.

        Parameters
        ----------
        target:
            IP address, hostname, or CIDR range to scan.
        flags:
            Additional nmap flags (default: ``-sV -sC``).

        Returns
        -------
        dict
            ``{"success": bool, "stdout": str, "stderr": str}``
        """
        if not await self.is_available():
            return self._unavailable_result()
        cmd = f"nmap {flags} {target}"
        return await self.run_command(cmd)

    async def run_sqlmap(self, target_url: str, flags: str = "") -> Dict:
        """
        Run sqlmap against *target_url* inside the sandbox.

        Parameters
        ----------
        target_url:
            URL to test for SQL injection.
        flags:
            Additional sqlmap flags.

        Returns
        -------
        dict
            ``{"success": bool, "stdout": str, "stderr": str}``
        """
        if not await self.is_available():
            return self._unavailable_result()
        cmd = f"sqlmap -u {target_url} {flags} --batch"
        return await self.run_command(cmd)

    async def run_hydra(self, target: str, service: str, wordlist: str) -> Dict:
        """
        Run hydra brute-force against *target*/*service* inside the sandbox.

        Parameters
        ----------
        target:
            Target IP or hostname.
        service:
            Service to attack (e.g. ``ssh``, ``ftp``, ``http-post-form``).
        wordlist:
            Path to the wordlist file **inside the container** (e.g.
            ``/phantom-data/passwords.txt``).

        Returns
        -------
        dict
            ``{"success": bool, "stdout": str, "stderr": str}``
        """
        if not await self.is_available():
            return self._unavailable_result()
        cmd = f"hydra -P {wordlist} {target} {service}"
        return await self.run_command(cmd)

    async def run_john(self, hash_file: str, wordlist: str = "") -> Dict:
        """
        Run John the Ripper against *hash_file* inside the sandbox.

        Parameters
        ----------
        hash_file:
            Path to the hash file **inside the container**.
        wordlist:
            Optional path to a wordlist file inside the container.

        Returns
        -------
        dict
            ``{"success": bool, "stdout": str, "stderr": str}``
        """
        if not await self.is_available():
            return self._unavailable_result()
        wordlist_flag = f"--wordlist={wordlist}" if wordlist else ""
        cmd = f"john {wordlist_flag} {hash_file}"
        return await self.run_command(cmd)

    async def run_hashcat(
        self, hash_file: str, mode: int = 0, wordlist: str = ""
    ) -> Dict:
        """
        Run hashcat against *hash_file* inside the sandbox.

        Parameters
        ----------
        hash_file:
            Path to the hash file **inside the container**.
        mode:
            Hashcat attack mode (default: ``0`` — dictionary attack).
        wordlist:
            Path to the wordlist file inside the container.

        Returns
        -------
        dict
            ``{"success": bool, "stdout": str, "stderr": str}``
        """
        if not await self.is_available():
            return self._unavailable_result()
        wordlist_arg = wordlist if wordlist else ""
        cmd = f"hashcat -m {mode} {hash_file} {wordlist_arg} --force"
        return await self.run_command(cmd)

    async def run_metasploit(self, resource_script: str) -> Dict:
        """
        Run msfconsole with *resource_script* inside the sandbox.

        Parameters
        ----------
        resource_script:
            Path to the Metasploit resource script **inside the container**.

        Returns
        -------
        dict
            ``{"success": bool, "stdout": str, "stderr": str}``
        """
        if not await self.is_available():
            return self._unavailable_result()
        cmd = f"msfconsole -q -r {resource_script}"
        return await self.run_command(cmd, timeout=300)

    async def run_impacket(self, tool: str, args: str) -> Dict:
        """
        Run an impacket tool inside the sandbox.

        Parameters
        ----------
        tool:
            Impacket tool name (e.g. ``GetUserSPNs``, ``secretsdump``).
        args:
            Arguments to pass to the tool.

        Returns
        -------
        dict
            ``{"success": bool, "stdout": str, "stderr": str}``
        """
        if not await self.is_available():
            return self._unavailable_result()
        cmd = f"impacket-{tool} {args}"
        return await self.run_command(cmd)

    # ------------------------------------------------------------------
    # File transfer
    # ------------------------------------------------------------------

    async def upload_file(self, local_path: str, container_path: str) -> Dict:
        """
        Copy a file from the host into the container.

        Uses the Docker SDK ``put_archive`` API to stream a tar archive
        containing the file into the container at *container_path*.

        Parameters
        ----------
        local_path:
            Absolute or relative path to the file on the host.
        container_path:
            Destination path **inside the container** (e.g.
            ``/phantom-data/payload.bin``).

        Returns
        -------
        dict
            ``{"success": True}`` on success or
            ``{"success": False, "error": str}`` on failure.
        """
        if not await self.is_available():
            return self._unavailable_result()

        if self._container is None:
            return self._container_not_running_result()

        try:
            local_path = os.path.expanduser(local_path)
            if not os.path.isfile(local_path):
                return {
                    "success": False,
                    "error": f"Local file not found: {local_path}",
                }

            container_dir = os.path.dirname(container_path)
            filename = os.path.basename(container_path)

            # Build an in-memory tar archive
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                tar.add(local_path, arcname=filename)
            buf.seek(0)

            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._container.put_archive(container_dir, buf),
            )
            logger.debug("Uploaded %s → %s", local_path, container_path)
            return {"success": True}

        except Exception as exc:
            logger.error("Error uploading file to container: %s", exc)
            return {"success": False, "error": str(exc)}

    async def download_file(self, container_path: str, local_path: str) -> Dict:
        """
        Copy a file from the container to the host.

        Uses the Docker SDK ``get_archive`` API to stream a tar archive
        from the container and extract it to *local_path*.

        Parameters
        ----------
        container_path:
            Path to the file **inside the container**.
        local_path:
            Destination path on the host.

        Returns
        -------
        dict
            ``{"success": True}`` on success or
            ``{"success": False, "error": str}`` on failure.
        """
        if not await self.is_available():
            return self._unavailable_result()

        if self._container is None:
            return self._container_not_running_result()

        try:
            local_path = os.path.expanduser(local_path)
            local_dir = os.path.dirname(local_path)
            if local_dir:
                os.makedirs(local_dir, exist_ok=True)

            bits, _stat = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._container.get_archive(container_path),
            )

            # Extract the single file from the tar stream
            buf = io.BytesIO()
            for chunk in bits:
                buf.write(chunk)
            buf.seek(0)

            with tarfile.open(fileobj=buf, mode="r") as tar:
                members = tar.getmembers()
                if not members:
                    return {
                        "success": False,
                        "error": f"No files found at container path: {container_path}",
                    }
                # Extract the first (and typically only) member
                member = members[0]
                extracted = tar.extractfile(member)
                if extracted is None:
                    return {
                        "success": False,
                        "error": f"Cannot extract file from container: {container_path}",
                    }
                with open(local_path, "wb") as fh:
                    fh.write(extracted.read())

            logger.debug("Downloaded %s → %s", container_path, local_path)
            return {"success": True}

        except Exception as exc:
            logger.error("Error downloading file from container: %s", exc)
            return {"success": False, "error": str(exc)}
