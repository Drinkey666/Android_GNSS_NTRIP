"""Bounded NTRIP recording with dechunked RTCM, arrival timeline and no saved credentials."""
import argparse
import base64
import csv
import getpass
import hashlib
import io
import json
import re
import socket
import ssl
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ['seq', 'utc_ns', 'elapsed_ns', 'channel', 'event', 'offset', 'length', 'reason']
RAW_NAMES = ['ssr.rtcm3', 'broadcast.rtcm3']


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def crc24(data):
    c = 0
    for b in data:
        c ^= b << 16
        for _ in range(8):
            c <<= 1
            if c & 0x1000000:
                c ^= 0x1864cfb
    return c & 0xffffff


class RtcmScanner:
    def __init__(self):
        self.buffer = bytearray()
        self.types = Counter()
        self.igs_subtypes = Counter()
        self.frames = self.crc_errors = self.discarded = 0

    def feed(self, data):
        self.buffer.extend(data)
        while len(self.buffer) >= 3:
            b = self.buffer
            if b[0] != 0xd3 or b[1] & 0xfc:
                del b[0]; self.discarded += 1; continue
            n = ((b[1] & 3) << 8) + b[2] + 6
            if len(b) < n:
                break
            if crc24(b[:n-3]) != int.from_bytes(b[n-3:n], 'big'):
                del b[0]; self.crc_errors += 1; continue
            if n >= 8:
                typ = b[3] * 16 + (b[4] >> 4)
                self.types[typ] += 1
                if typ == 4076 and n >= 9:
                    self.igs_subtypes[(int.from_bytes(b[3:6], 'big') >> 1) & 255] += 1
            self.frames += 1
            del b[:n]

    def reset(self):
        self.buffer.clear()  # a TCP discontinuity must not join two partial RTCM frames

    def summary(self):
        return dict(valid_rtcm_frames=self.frames, crc_failures=self.crc_errors,
                    discarded_bytes=self.discarded, message_types=dict(sorted(self.types.items())),
                    igs_subtypes=dict(sorted(self.igs_subtypes.items())))


class ProtocolError(Exception):
    pass


WHU_SSR_PROFILES = ('WHU_OSB_CONTINUITY_V1', 'WHU_OSB_FIRST_COMPLETE_V2')


def validate_ssr_profile(c, profile):
    if profile not in ('GENERIC_STRICT', *WHU_SSR_PROFILES):
        raise ValueError('SSR_PROFILE_INVALID')
    if profile in WHU_SSR_PROFILES and (c['ssr_mount']!='SSRC00WHU0' or
        c.get('bias_mount')!='OSBC00WHU1' or c['orbit_reference']!='COM'):
        raise ValueError('WHU_PROFILE_ENDPOINT_OR_DATUM_INVALID')


def endpoint_for_mount(config, mount):
    if mount == config['broadcast_mount'] and 'anonymous_broadcast_endpoint' in config:
        return config['anonymous_broadcast_endpoint'], True
    return config, False


def validate_endpoint(c):
    if not isinstance(c.get('host'), str) or not re.fullmatch(r'[A-Za-z0-9.-]{1,253}', c['host']):
        raise ValueError('HOST_INVALID')
    if type(c.get('port')) is not int or not 1 <= c['port'] <= 65535:
        raise ValueError('PORT_INVALID')
    if type(c.get('tls')) is not bool:
        raise ValueError('TLS_INVALID')


def validate_config(c):
    allowed = {'host', 'port', 'tls', 'ssr_mount', 'broadcast_mount', 'orbit_reference', 'reference_pairs', 'bias_mount','ssr_profile','anonymous_broadcast_endpoint'}
    if set(c) - allowed:
        raise ValueError('Unknown caster fields; credentials do not belong in the configuration')
    validate_endpoint(c)
    if 'anonymous_broadcast_endpoint' in c:
        nav = c['anonymous_broadcast_endpoint']
        if not isinstance(nav, dict) or set(nav) != {'host', 'port', 'tls'}:
            raise ValueError('INVALID_ANONYMOUS_BROADCAST_ENDPOINT')
        validate_endpoint(nav)
    for k in ('ssr_mount', 'broadcast_mount') + (('bias_mount',) if c.get('bias_mount') else ()):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', c.get(k, '')):
            raise ValueError('MOUNT_INVALID')
    if c['ssr_mount'] == c['broadcast_mount']:
        raise ValueError('MOUNTS_MUST_DIFFER')
    if c.get('bias_mount') in (c['ssr_mount'],c['broadcast_mount']):
        raise ValueError('MOUNTS_MUST_DIFFER')
    validate_ssr_profile(c, c.get('ssr_profile','GENERIC_STRICT'))
    if c.get('orbit_reference') not in ('APC', 'COM') or type(c.get('tls')) is not bool:
        raise ValueError('DATUM_OR_TLS_INVALID')
    pairs = c.get('reference_pairs')
    if pairs != {'GPS': ['1W', '2W'], 'GAL': ['1C', '5Q'], 'BDS': ['2I', '6I']}:
        raise ValueError('UNSUPPORTED_SSR_CLOCK_REFERENCE_PAIRS')
    return c


def _line(source, limit=4096):
    b = source.readline(limit + 2)
    if not b.endswith(b'\n') or len(b) > limit:
        raise ProtocolError('HEADER_OR_CHUNK_LINE_INVALID')
    return b.rstrip(b'\r\n')


class NtripBody:
    def __init__(self, source):
        self.source = source
        self.left = 0
        self.terminator = self.ended = self.chunked = False
        status = _line(source, 1024).decode('ascii', errors='replace').split()
        if len(status) < 2 or status[0] == 'SOURCETABLE':
            raise ProtocolError('SOURCETABLE_NOT_RTCM')
        if status[0] != 'ICY' and not status[0].startswith('HTTP/1.'):
            raise ProtocolError('BAD_RESPONSE')
        if status[1] != '200':
            raise ProtocolError('HTTP_' + (status[1] if status[1].isdigit() else 'INVALID'))
        self.status = '200'
        if status[0] == 'ICY' and source.peek(1)[:1] == b'\xd3':
            return
        headers = {}; size = 0
        while True:
            line = _line(source); size += len(line) + 2
            if size > 16384:
                raise ProtocolError('HEADER_TOO_LARGE')
            if not line:
                break
            name, sep, value = line.partition(b':')
            key = name.strip().lower()
            if not sep or key in headers:
                raise ProtocolError('HEADER_INVALID')
            headers[key] = value.strip().lower()
        if b'text' in headers.get(b'content-type', b''):
            raise ProtocolError('TEXT_NOT_RTCM')
        if headers.get(b'content-encoding', b'identity') != b'identity':
            raise ProtocolError('UNSUPPORTED_ENCODING')
        transfer = headers.get(b'transfer-encoding', b'')
        if transfer not in (b'', b'chunked'):
            raise ProtocolError('UNSUPPORTED_TRANSFER')
        self.chunked = transfer == b'chunked'

    def read(self, limit=16384):
        if self.ended:
            return b''
        if not self.chunked:
            return self.source.read1(limit)
        if not self.left:
            if self.terminator and _line(self.source, 2) != b'':
                raise ProtocolError('BAD_CHUNK_END')
            line = _line(self.source, 128).split(b';', 1)[0].strip()
            if not re.fullmatch(rb'[0-9a-fA-F]{1,8}', line):
                raise ProtocolError('BAD_CHUNK_SIZE')
            self.left = int(line, 16)
            if self.left > 8 * 1024 * 1024:
                raise ProtocolError('CHUNK_TOO_LARGE')
            if not self.left:
                for _ in range(17):
                    if not _line(self.source, 1024):
                        self.ended = True; return b''
                raise ProtocolError('TRAILERS_TOO_LARGE')
            self.terminator = True
        data = self.source.read1(min(limit, self.left))
        if not data:
            raise ProtocolError('TRUNCATED_CHUNK')
        self.left -= len(data)
        return data


class CaptureWriter:
    def __init__(self, directory, max_bytes, raw_names=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.raw_names = raw_names or RAW_NAMES
        self.raw = [(self.directory / n).open('xb') for n in self.raw_names]
        self.csv_file = (self.directory / 'arrivals.csv').open('x', newline='', encoding='ascii')
        self.csv = csv.writer(self.csv_file); self.csv.writerow(FIELDS)
        self.lock = threading.Lock()
        self.start_utc = time.time_ns(); self.start_mono = time.monotonic_ns()
        self.max_bytes = max_bytes; self.seq = self.total = 0
        self.scanners = [RtcmScanner() for _ in self.raw_names]
        self.last_utc = self.start_utc
        self.started = datetime.now(timezone.utc).isoformat()

    def write(self, channel, event, data=b'', reason=''):
        with self.lock:
            elapsed = time.monotonic_ns() - self.start_mono
            arrival = self.start_utc + elapsed
            if abs(time.time_ns() - arrival) > 500_000_000:
                raise ProtocolError('PC_CLOCK_STEP_STOP_RECORDING')
            if self.total + len(data) > self.max_bytes:
                raise ProtocolError('SIZE_LIMIT_REACHED')
            offset = self.raw[channel].tell()
            if data:
                self.raw[channel].write(data); self.raw[channel].flush()
                self.scanners[channel].feed(data); self.total += len(data)
            if event == 'RESET':
                self.scanners[channel].reset()
            self.csv.writerow([self.seq, arrival, elapsed, channel, event, offset, len(data), reason])
            self.csv_file.flush(); self.seq += 1; self.last_utc = arrival

    def close(self):
        for f in self.raw:
            f.close()
        self.csv_file.close()


def record(config, directory, seconds, max_mib, user, password):
    validate_config(config)
    if ':' in user or '\r' in user or '\n' in user or '\r' in password or '\n' in password:
        raise ValueError('AUTH_FORMAT_INVALID')
    if not 0 < seconds <= 86400 or not 0 < max_mib <= 4096:
        raise ValueError('DURATION_OR_SIZE_INVALID')
    raw_names=RAW_NAMES+(['bias.rtcm3'] if config.get('bias_mount') else [])
    mounts = [config['ssr_mount'], config['broadcast_mount']]+([config['bias_mount']] if config.get('bias_mount') else [])
    writer = CaptureWriter(directory, int(max_mib * 1024 * 1024),raw_names)
    manifest_path = writer.directory / 'capture.json'
    manifest = dict(format='PPP_NTRIP_CAPTURE_V2' if len(mounts)==3 else 'PPP_NTRIP_CAPTURE_V1', complete=False, config=config,
                    pc_clock_sync_verified=False, clock='UTC anchor + monotonic elapsed; verify PC UTC externally',
                    start_utc_ns=writer.start_utc, duration_limit_seconds=seconds, max_mib=max_mib,
                    credential_storage='NONE', streams=[{} for _ in mounts])
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    stop = threading.Event(); sockets = [None for _ in mounts]; lock = threading.Lock(); failures = []

    def worker(channel):
        endpoint, anonymous = endpoint_for_mount(config, mounts[channel])
        delay = 1
        while not stop.is_set():
            sock = source = None
            try:
                writer.write(channel, 'RESET')
                sock = socket.socket(); sock.settimeout(10)
                with lock:
                    sockets[channel] = sock
                    if stop.is_set():
                        sock.close(); return
                sock.connect((endpoint['host'], endpoint['port']))
                if endpoint['tls']:
                    sock = ssl.create_default_context().wrap_socket(sock, server_hostname=endpoint['host'])
                    with lock:
                        sockets[channel] = sock
                        if stop.is_set():
                            sock.close(); return
                auth = base64.b64encode((user + ':' + password).encode('utf-8')).decode('ascii') if user and not anonymous else ''
                request = f"GET /{mounts[channel]} HTTP/1.1\r\nHost: {endpoint['host']}:{endpoint['port']}\r\n"
                request += 'Ntrip-Version: Ntrip/2.0\r\nUser-Agent: NTRIP PPP-PC/1.0\r\nAccept-Encoding: identity\r\n'
                if auth:
                    request += f'Authorization: Basic {auth}\r\n'
                sock.sendall((request + 'Connection: close\r\n\r\n').encode('ascii'))
                del auth, request
                sock.settimeout(60)  # The caster may queue an authenticated mount request.
                source = sock.makefile('rb'); body = NtripBody(source)
                sock.settimeout(15)
                manifest['streams'][channel].update(http_status=200, mount=mounts[channel])
                writer.write(channel, 'CONNECTED')
                print(f"channel={channel} mount={mounts[channel]} HTTP=200", flush=True)
                while not stop.is_set():
                    data = body.read()
                    if not data:
                        raise EOFError()
                    writer.write(channel, 'DATA', data); delay = 1
            except Exception as exc:
                reason = str(exc) if isinstance(exc, ProtocolError) else type(exc).__name__
                if not stop.is_set():
                    failures.append(dict(channel=channel, reason=reason))
                    try:
                        writer.write(channel, 'CLOSED', reason=reason)
                    except ProtocolError:
                        stop.set()
                    print(f'channel={channel} status={reason}', flush=True)
                    if reason.startswith('HTTP_4') or reason in ('SOURCETABLE_NOT_RTCM', 'PC_CLOCK_STEP_STOP_RECORDING', 'SIZE_LIMIT_REACHED'):
                        stop.set()
            finally:
                if source:
                    source.close()
                if sock:
                    sock.close()
                with lock:
                    sockets[channel] = None
            if stop.wait(delay):
                break
            delay = min(delay * 2, 30)

    threads = [threading.Thread(target=worker, args=(i,), name=f'NTRIP-{i}', daemon=True) for i in range(len(mounts))]
    for i in range(len(mounts)):
        writer.write(i, 'START')
    for t in threads:
        t.start()
    try:
        stop.wait(seconds)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        with lock:
            for sock in sockets:
                if sock:
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    sock.close()
        for t in threads:
            t.join(12)
        if any(t.is_alive() for t in threads):
            raise RuntimeError('WORKER_DID_NOT_STOP_CAPTURE_NOT_FINALIZED')
        for i in range(len(mounts)):
            try:
                writer.write(i, 'END')
            except ProtocolError as exc:
                failures.append(dict(channel=i, reason=str(exc)))
        writer.close()
    manifest.update(complete=True, end_utc_ns=writer.last_utc, actual_seconds=(writer.last_utc-writer.start_utc)/1e9,
                    total_bytes=writer.total, failures=failures, streams=[
                        dict(manifest['streams'][i], **writer.scanners[i].summary(), bytes=(writer.directory/raw_names[i]).stat().st_size)
                        for i in range(len(mounts))],
                    files={n:dict(bytes=(writer.directory/n).stat().st_size, sha256=sha(writer.directory/n))
                           for n in raw_names + ['arrivals.csv']})
    manifest['transport_received_both'] = all(s['valid_rtcm_frames'] > 0 for s in manifest['streams'])
    manifest['ppp_ready'] = False  # availability is evaluated per observation epoch by RTKLIB
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', type=Path, default=ROOT/'config/caster_whu.json')
    ap.add_argument('--out', type=Path)
    ap.add_argument('--seconds', type=float, default=1800)
    ap.add_argument('--max-mib', type=float, default=128)
    args = ap.parse_args()
    try:
        c = validate_config(json.loads(args.config.read_text(encoding='utf-8-sig')))
        out = args.out or ROOT/'sessions'/datetime.now().strftime('%Y%m%d_%H%M%S')
        user = input('NTRIP user (session only): ').strip()
        password = getpass.getpass('NTRIP password (not saved): ') if user else ''
        result = record(c, out, args.seconds, args.max_mib, user, password)
        print(json.dumps(dict(capture=str(out.resolve()), bytes=result['total_bytes'],
                              both_streams=result['transport_received_both'],
                              frames=[s['valid_rtcm_frames'] for s in result['streams']])))
        return 0 if result['transport_received_both'] else 2
    except (ValueError, OSError, ProtocolError) as exc:
        # Exception text from remote responses or auth is never printed.
        print('CAPTURE_FAILED: ' + type(exc).__name__)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
