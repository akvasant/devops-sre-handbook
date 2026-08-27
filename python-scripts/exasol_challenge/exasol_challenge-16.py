#!/usr/bin/env python3

import argparse
import hashlib
import multiprocessing
import os
import queue
import socket
import ssl
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


SERVER_HOST = "18.202.148.130"
SERVER_PORTS = [3336, 8083, 8446, 49155, 3481, 65532]

CONNECT_TIMEOUT_SECONDS = 15
PROTOCOL_TIMEOUT_SECONDS = 6
POW_STOP_CHECK_INTERVAL = 65_536
POW_TIMEOUT_SECONDS = 2 * 60 * 60

@dataclass(frozen=True)
class Applicant:
    name: str
    emails: list[str]
    skype: str
    birthdate: str
    country: str
    address_lines: list[str]

APPLICANT = Applicant(
    name="Vasanth Arcot Kanniappan",
    emails=[
        "vasanth_qe@yahoo.co.in",
    ],
    skype="N/A",
    birthdate="08.11.1983",
    country="India",
    address_lines=[
        "89A, 6th Street, Ram Nagar, Velachery",
        "Chennai, Tamil Nadu, 600042",
    ],
)

def sha1_hex(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()

def write_line(connection: ssl.SSLSocket, value: str) -> None:
    if "\n" in value or "\r" in value:
        raise ValueError("Protocol responses cannot contain CR/LF characters")
    connection.sendall((value + "\n").encode("utf-8"))

def read_line(connection: ssl.SSLSocket, buffer: bytearray) -> Optional[str]:
    while True:
        newline_position = buffer.find(b"\n")
        if newline_position >= 0:
            raw_line = bytes(buffer[:newline_position])
            del buffer[: newline_position + 1]
            return raw_line.rstrip(b"\r").decode("utf-8")
        chunk = connection.recv(4096)
        if not chunk:
            if buffer:
                raw_line = bytes(buffer)
                buffer.clear()
                return raw_line.decode("utf-8")
            return None
        buffer.extend(chunk)

def digest_has_leading_hex_zeros(digest: bytes, difficulty: int) -> bool:
    full_zero_bytes, odd_nibble = divmod(difficulty, 2)
    if full_zero_bytes and digest[:full_zero_bytes] != b"\x00" * full_zero_bytes:
        return False
    if odd_nibble:
        return digest[full_zero_bytes] < 0x10
    return True

def pow_worker(
    authdata: str,
    difficulty: int,
    worker_number: int,
    worker_count: int,
    stop_event,
    result_queue,
) -> None:
    base_hash = hashlib.sha1(authdata.encode("utf-8"))
    counter = worker_number
    attempts = 0
    while not stop_event.is_set():
        # Avoid an inter-process Event lookup on every single hash.
        for _ in range(POW_STOP_CHECK_INTERVAL):
            suffix = format(counter, "x")
            candidate_hash = base_hash.copy()
            candidate_hash.update(suffix.encode("ascii"))
            digest = candidate_hash.digest()
            attempts += 1
            if digest_has_leading_hex_zeros(digest, difficulty):
                try:
                    result_queue.put_nowait(
                        (suffix, worker_number, attempts, digest.hex())
                    )
                except queue.Full:
                    pass
                stop_event.set()
                return
            counter += worker_count
        # Another process may have found a solution during this batch.
        if stop_event.is_set():
            return

def solve_proof_of_work(
    authdata: str,
    difficulty: int,
    process_count: Optional[int] = None,
) -> str:
    if not 0 <= difficulty <= 40:
        raise ValueError(f"Invalid SHA-1 difficulty: {difficulty}")
    if difficulty == 0:
        return "0"
    if process_count is None:
        process_count = os.cpu_count() or 1
    process_count = max(1, process_count)
    print(
        f"Solving POW difficulty={difficulty} "
        f"with {process_count} process(es)...",
        flush=True,
    )
    stop_event = multiprocessing.Event()
    result_queue = multiprocessing.Queue(maxsize=1)
    workers = [
        multiprocessing.Process(
            target=pow_worker,
            args=(
                authdata,
                difficulty,
                worker_number,
                process_count,
                stop_event,
                result_queue,
            ),
            name=f"pow-{worker_number}",
        )
        for worker_number in range(process_count)
    ]
    for worker in workers:
        worker.start()
    result = None
    start_time = time.monotonic()
    try:
        while result is None:
            # Stop POW if Exasol's 2-hour timeout is reached
            if time.monotonic() - start_time >= POW_TIMEOUT_SECONDS:
                raise TimeoutError(
                    "POW could not be solved within the 2-hour timeout"
                )
            try:
                result = result_queue.get(timeout=1)
            except queue.Empty:
                if not any(worker.is_alive() for worker in workers):
                    raise RuntimeError(
                        "All POW workers exited without returning a solution"
                    )
    except KeyboardInterrupt:
        stop_event.set()
        raise
    finally:
        stop_event.set()
        for worker in workers:
            worker.join(timeout=2)
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join()
        result_queue.close()
        result_queue.join_thread()
    suffix, worker_number, attempts, digest_hex = result
    # Final independent verification before anything is sent.
    verified_digest = hashlib.sha1(
        (authdata + suffix).encode("utf-8")
    ).digest()
    if not digest_has_leading_hex_zeros(verified_digest, difficulty):
        raise RuntimeError("Internal POW verification failed")
    print(
        f"POW solved by worker {worker_number}; "
        f"worker attempts={attempts:,}; "
        f"suffix={suffix}; SHA1={digest_hex}",
        flush=True,
    )
    return suffix

def create_tls_context(
    certificate_path: str,
    private_key_path: str,
    ca_path: Optional[str],
) -> ssl.SSLContext:
    context = ssl.create_default_context(
        cafile=ca_path if ca_path else None
    )
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(
        certfile=certificate_path,
        keyfile=private_key_path,
    )
    return context

def connect_to_server(context: ssl.SSLContext, ports: list[int], server_name: str,) -> tuple[ssl.SSLSocket, int]:
    last_error: Optional[Exception] = None
    for port in ports:
        raw_socket: Optional[socket.socket] = None
        try:
            print(f"Connecting to {SERVER_HOST}:{port}...", flush=True)
            raw_socket = socket.create_connection(
                (SERVER_HOST, port),
                timeout=CONNECT_TIMEOUT_SECONDS,
            )
            tls_socket = context.wrap_socket(
                raw_socket,
                server_hostname=server_name,
            )
            # All non-POW protocol commands have a six-second timeout.
            tls_socket.settimeout(PROTOCOL_TIMEOUT_SECONDS)
            print(
                f"TLS connected on port {port}; "
                f"protocol={tls_socket.version()}",
                flush=True,
            )
            return tls_socket, port
        except (OSError, ssl.SSLError) as error:
            last_error = error
            if raw_socket is not None:
                try:
                    raw_socket.close()
                except OSError:
                    pass
            print(f"Port {port} failed: {error}", file=sys.stderr)
    raise ConnectionError(
        f"Unable to connect on any documented port: {last_error}"
    )

def signed_response(authdata: str, challenge: str, value: str) -> str:
    """Return: SHA1(authdata + challenge) + space + response value."""
    return f"{sha1_hex(authdata + challenge)} {value}"

def handle_protocol(connection: ssl.SSLSocket, applicant: Applicant, process_count: Optional[int],) -> bool:
    buffer = bytearray()
    authdata: Optional[str] = None
    while True:
        line = read_line(connection, buffer)
        if line is None:
            print(
                "Server closed the connection before END.",
                file=sys.stderr,
            )
            return False
        # Remove only protocol CR/LF already handled above; preserve other
        # characters rather than broadly stripping server content.
        if not line:
            continue
        print(f"SERVER: {line}", flush=True)
        args = line.split(" ")
        command = args[0]
        if command == "HELO":
            write_line(connection, "TOAKUEI")
            print("CLIENT: TOAKUEI", flush=True)
            continue
        if command == "ERROR":
            error_message = " ".join(args[1:])
            print(f"Server error: {error_message}", file=sys.stderr)
            return False
        if command == "POW":
            if len(args) != 3:
                raise RuntimeError(f"Malformed POW command: {line!r}")
            authdata = args[1]
            try:
                difficulty = int(args[2])
            except ValueError as exc:
                raise RuntimeError(
                    f"Invalid POW difficulty: {args[2]!r}"
                ) from exc
            suffix = solve_proof_of_work(
                authdata=authdata,
                difficulty=difficulty,
                process_count=process_count,
            )
            write_line(connection, suffix)
            print(f"CLIENT: POW suffix {suffix}", flush=True)
            continue
        if command == "END":
            write_line(connection, "OK")
            print("CLIENT: OK", flush=True)
            print(
                "SUCCESS: server sent END; application data was submitted.",
                flush=True,
            )
            return True
        if authdata is None:
            raise RuntimeError(
                f"Received {command!r} before POW authentication"
            )
        if len(args) < 2 or not args[1]:
            raise RuntimeError(f"Missing challenge token: {line!r}")
        challenge = args[1]
        if command == "NAME":
            value = applicant.name
        elif command == "MAILNUM":
            value = str(len(applicant.emails))
        elif command.startswith("MAIL") and command[4:].isdigit():
            email_number = int(command[4:])
            if not 1 <= email_number <= len(applicant.emails):
                raise RuntimeError(
                    f"Server requested unavailable email: {command}"
                )
            value = applicant.emails[email_number - 1]
        elif command == "SKYPE":
            value = applicant.skype
        elif command == "BIRTHDATE":
            value = applicant.birthdate
        elif command == "COUNTRY":
            value = applicant.country
        elif command == "ADDRNUM":
            value = str(len(applicant.address_lines))
        elif command.startswith("ADDRLINE"):
            number_text = command.removeprefix("ADDRLINE")
            if not number_text.isdigit():
                raise RuntimeError(
                    f"Unexpected address command: {command}"
                )
            line_number = int(number_text)
            if not 1 <= line_number <= len(applicant.address_lines):
                raise RuntimeError(
                    f"Server requested unavailable address line: {command}"
                )
            value = applicant.address_lines[line_number - 1]
        else:
            raise RuntimeError(f"Unsupported server command: {command}")
        response = signed_response(authdata, challenge, value)
        write_line(connection, response)
        # Avoid printing birth date/address contents in logs.
        print(f"CLIENT: responded to {command}", flush=True)

def validate_applicant(applicant: Applicant) -> None:
    if len(applicant.name.strip().split()) < 2:
        raise ValueError("NAME must contain at least first and last name")
    if not applicant.emails:
        raise ValueError("At least one email address is required")
    for email in applicant.emails:
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            raise ValueError(f"Email appears invalid: {email!r}")
    try:
        datetime.strptime(applicant.birthdate, "%d.%m.%Y")
    except ValueError as exc:
        raise ValueError(
            "BIRTHDATE must be a valid date in DD.MM.YYYY format"
        ) from exc
    if not applicant.country.strip():
        raise ValueError("COUNTRY is required")
    if not applicant.address_lines:
        raise ValueError("At least one address line is required")
    all_values = [
        applicant.name,
        *applicant.emails,
        applicant.skype,
        applicant.birthdate,
        applicant.country,
        *applicant.address_lines,
    ]
    for value in all_values:
        if "\n" in value or "\r" in value:
            raise ValueError(
                "Applicant fields cannot contain CR/LF characters"
            )

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exasol application challenge client"
    )
    parser.add_argument(
        "--cert",
        required=True,
        help="Path to the client TLS certificate",
    )
    parser.add_argument(
        "--key",
        required=True,
        help="Path to the client TLS private key",
    )
    parser.add_argument(
        "--ca",
        help="Optional CA bundle supplied for the challenge",
    )
    parser.add_argument(
        "--server-name",
        default=SERVER_HOST,
        help=(
            "TLS server name used for certificate verification. "
            "Use the DNS name from the README/certificate if one is supplied."
        ),
    )
    parser.add_argument(
        "--processes",
        type=int,
        default=os.cpu_count() or 1,
        help="Number of CPU processes used for POW",
    )
    parser.add_argument(
        "--port",
        type=int,
        action="append",
        help="Port to try; may be supplied more than once",
    )
    arguments = parser.parse_args()
    if arguments.processes < 1:
        parser.error("--processes must be at least 1")
    validate_applicant(APPLICANT)
    ports = arguments.port or SERVER_PORTS
    context = create_tls_context(
        certificate_path=arguments.cert,
        private_key_path=arguments.key,
        ca_path=arguments.ca,
    )
    connection: Optional[ssl.SSLSocket] = None
    try:
        connection, connected_port = connect_to_server(
            context=context,
            ports=ports,
            server_name=arguments.server_name,
        )
        successful = handle_protocol(
            connection=connection,
            applicant=APPLICANT,
            process_count=arguments.processes,
        )
        if successful:
            print(f"Completed through port {connected_port}")
            return 0
        return 1
    except socket.timeout:
        print(
            "Protocol timed out while waiting for the server.",
            file=sys.stderr,
        )
        return 1
    except (
        ConnectionError,
        OSError,
        ssl.SSLError,
        UnicodeError,
        ValueError,
        RuntimeError,
    ) as error:
        print(f"Challenge failed: {error}", file=sys.stderr)
        return 1
    finally:
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())