"""Bounded PC NTRIP probe. Receipt requires a CRC24Q-valid RTCM3 frame.

Credentials follow observe_whu_continuity.py's local-properties convention;
there are deliberately no username/password command-line options.
"""
import argparse
import base64
import errno
import getpass
import io
import ipaddress
import json
import queue
import re
import socket
import ssl
import struct
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

def find_project_root(script_path=None, working_directory=None, explicit=None):
    """Locate dependencies/config even when this entry script has been copied."""
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    else:
        for directory in (Path(script_path or __file__).resolve().parent,
                          Path(working_directory or Path.cwd()).resolve()):
            candidates.extend((directory, *directory.parents))
        candidates.append(Path('E:/GNSS/PPP_NTRIP_PC'))
    for candidate in candidates:
        if ((candidate/'tools/ntrip_capture.py').is_file() and
                (candidate/'config/caster_whu.json').is_file()):
            return candidate.resolve()
    raise ValueError('PROJECT_ROOT_NOT_FOUND')


_bootstrap_parser = argparse.ArgumentParser(add_help=False)
_bootstrap_parser.add_argument('--project-root', type=Path)
_bootstrap_args, _ = _bootstrap_parser.parse_known_args()
try:
    ROOT = find_project_root(explicit=_bootstrap_args.project_root)
except ValueError:
    raise SystemExit('找不到 PPP_NTRIP_PC 工程；请用 --project-root 指定包含 tools/ 和 config/ 的项目根目录。') from None
sys.path.insert(0, str(ROOT/'tools'))
from ntrip_capture import NtripBody, ProtocolError, RtcmScanner, endpoint_for_mount, validate_config

BEIJING = timezone(timedelta(hours=8))
TCP_TIMEOUT = 10.0
HEADER_TIMEOUT = 15.0
LABELS = {
    'VALID_RTCM': '收到有效 RTCM', 'DNS_FAILED': 'DNS 失败',
    'TCP_TIMEOUT': 'TCP 建连超时', 'TCP_REFUSED': 'TCP 连接被拒绝',
    'TCP_ERROR': 'TCP 建连错误', 'BIND_ERROR': '本地 IP 绑定失败',
    'HEADER_TIMEOUT': '响应头超时', 'HEADER_INVALID': '响应头/协议无效',
    'HTTP_401': 'HTTP 401：认证未通过', 'HTTP_403': 'HTTP 403：访问被拒绝',
    'HTTP_404': '该挂载请求返回 404', 'SOURCETABLE': '返回源表',
    'SUCCESS_NO_BODY': '成功响应后零正文',
    'BODY_NO_VALID_RTCM': '收到正文但没有有效 RTCM 帧',
    'TLS_ERROR': 'TLS 握手失败', 'CREDENTIALS_ERROR': '本地凭据不可用',
    'NOT_TESTED': '未测试：共用入口无法建连',
    'NOT_TESTED_DNS': '未测试：共用 DNS 失败',
    'NOT_TESTED_CREDENTIALS': '未测试：共用凭据不可用',
}


def local_time():
    return datetime.now(BEIJING).isoformat(timespec='milliseconds')


def resolve(host, port, family=socket.AF_UNSPEC, timeout=10):
    """Bound DNS waiting without blocking process shutdown on a stuck resolver."""
    answer = queue.Queue()
    def worker():
        try:
            answer.put((True, socket.getaddrinfo(host, port, family, socket.SOCK_STREAM)))
        except OSError:
            answer.put((False, None))
    threading.Thread(target=worker, daemon=True).start()
    try:
        ok, records = answer.get(timeout=timeout)
    except queue.Empty:
        return {'addresses': [], 'error': 'DNS_TIMEOUT', 'method': 'system_getaddrinfo'}
    addresses = list(dict.fromkeys(r[4][0] for r in records)) if ok else []
    return {'addresses': addresses, 'error': None if addresses else 'DNS_FAILED',
            'method': 'system_getaddrinfo'}


def credentials(path=None):
    candidates = [path] if path else [ROOT/'ntrip.local.properties',
                                    Path('E:/android/test/PPP_NTRIP/ntrip.local.properties')]
    for candidate in candidates:
        if candidate and candidate.is_file():
            values = {}
            for line in candidate.read_text(encoding='utf-8-sig').splitlines():
                if '=' in line and not line.lstrip().startswith(('#', '!')):
                    key, value = line.split('=', 1)
                    values[key.strip()] = value.strip()
            user, password = values.get('ntrip.username', ''), values.get('ntrip.password', '')
            break
    else:
        if not sys.stdin.isatty():
            raise ValueError('CREDENTIALS_MISSING')
        user = getpass.getpass('NTRIP user (not echoed or saved): ')
        password = getpass.getpass('NTRIP password (not echoed or saved): ')
    if not user or not password or ':' in user or any(c in user+password for c in '\r\n'):
        raise ValueError('CREDENTIALS_INVALID')
    return user, password


def request_bytes(config, mount, user, password):
    """Same request format as tools/ntrip_capture.py::record()."""
    if ':' in user or any(c in user+password for c in '\r\n'):
        raise ValueError('AUTH_FORMAT_INVALID')
    auth = base64.b64encode((user+':'+password).encode('utf-8')).decode('ascii')
    header = f'Authorization: Basic {auth}\r\n' if user else ''
    return (f"GET /{mount} HTTP/1.1\r\nHost: {config['host']}:{config['port']}\r\n"
            'Ntrip-Version: Ntrip/2.0\r\nUser-Agent: NTRIP PPP-PC/1.0\r\n'
            'Accept-Encoding: identity\r\n'+header+'Connection: close\r\n\r\n').encode('ascii')


def interface_for_bind(address):
    if not address or sys.platform != 'win32':
        return None
    # address is canonicalized by ipaddress, so no shell syntax can enter here.
    code = (f"Get-NetIPAddress -IPAddress '{address}' -ErrorAction Stop | "
            'Select-Object -First 1 -ExpandProperty InterfaceIndex')
    out = subprocess.check_output(['powershell', '-NoProfile', '-Command', code],
                                  stderr=subprocess.DEVNULL, timeout=10)
    return int(out.decode().strip())


class Wire(io.RawIOBase):
    def __init__(self, sock, deadline, start):
        self.sock, self.deadline, self.start = sock, deadline, start
        self.count, self.first_s = 0, None
    def readable(self):
        return True
    def readinto(self, target):
        remaining = self.deadline-time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        self.sock.settimeout(remaining)
        data = self.sock.recv(len(target))
        if data:
            if self.first_s is None:
                self.first_s = time.monotonic()-self.start
            self.count += len(data)
            target[:len(data)] = data
        return len(data)


class StatusReader(io.BufferedReader):
    def __init__(self, wire, row):
        super().__init__(wire)
        self.row, self.first_line = row, True
    def readline(self, *args):
        data = super().readline(*args)
        if self.first_line:
            self.first_line = False
            words = data.split()
            protocol = words[0] if words else b''
            self.row['status_line_complete'] = data.endswith(b'\n')
            if protocol == b'SOURCETABLE':
                self.row['source_table'] = True
                self.row['protocol'] = 'SOURCETABLE'
            elif protocol in (b'ICY', b'HTTP/1.0', b'HTTP/1.1'):
                self.row['protocol'] = protocol.decode('ascii')
                if data.endswith(b'\n') and len(words)>1 and re.fullmatch(rb'\d{3}', words[1]):
                    self.row['status'] = words[1].decode('ascii')
        elif data.lower().startswith(b'content-type:') and b'sourcetable' in data.lower():
            self.row['source_table'] = True
        return data


def probe(config, mount, target, get_credentials, bind_ip=None, bind_index=None,
          seconds=30, tcp_timeout=TCP_TIMEOUT, header_timeout=HEADER_TIMEOUT,
          attempts=2, retry_delay=10):
    started = time.monotonic()
    row = dict(mount=mount, start_local=local_time(), target_ip=target, port=config['port'],
               status=None, protocol=None, tcp_connected=False, local_ip=None,
               remote_ip=None, first_valid_frame_s=None, first_body_s=None,
               body_bytes=0, tcp_attempts=[], source_table=False, headers_complete=False)
    scanner, wire, source, sock = RtcmScanner(), None, None, None
    stage, connection_start = 'tcp', started
    try:
        family = socket.AF_INET6 if ipaddress.ip_address(target).version==6 else socket.AF_INET
        for attempt in range(attempts):
            connection_start = time.monotonic()
            record = {'start_local': local_time(), 'connected': False}
            sock = socket.socket(family, socket.SOCK_STREAM)
            try:
                stage = 'bind'
                if bind_ip:
                    if bind_index is not None and family==socket.AF_INET and sys.platform=='win32':
                        sock.setsockopt(socket.IPPROTO_IP, 31, struct.pack('!I', bind_index))
                        row['forced_interface_index'] = struct.unpack('=I', sock.getsockopt(socket.IPPROTO_IP,31,4))[0]
                        if row['forced_interface_index'] != bind_index:
                            raise OSError('INTERFACE_READBACK_FAILED')
                    sock.bind((bind_ip, 0))
                stage = 'tcp'
                sock.settimeout(tcp_timeout)
                sock.connect((target, config['port']))
                record['connected'] = True
            except OSError as exc:
                record.update(error_type=type(exc).__name__, errno=exc.errno,
                              winerror=getattr(exc, 'winerror', None))
                try:
                    record['local_ip'], record['local_port'] = sock.getsockname()[:2]
                    row['local_ip'], row['local_port'] = record['local_ip'], record['local_port']
                except OSError:
                    pass
                row['conclusion'] = ('BIND_ERROR' if stage=='bind' else
                    'TCP_TIMEOUT' if isinstance(exc, TimeoutError) else
                    'TCP_REFUSED' if exc.errno in (errno.ECONNREFUSED,10061) or getattr(exc,'winerror',None)==10061 else 'TCP_ERROR')
                sock.close(); sock = None
            record['elapsed_s'] = time.monotonic()-connection_start
            row['tcp_attempts'].append(record)
            if record['connected']:
                row['tcp_connected'] = True
                row['local_ip'], row['local_port'] = sock.getsockname()[:2]
                row['remote_ip'] = sock.getpeername()[0]
                break
            if stage=='bind' or attempt+1==attempts:
                return row
            time.sleep(retry_delay)
        stage = 'tls'
        if config['tls']:
            sock.settimeout(tcp_timeout)
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=config['host'])
        stage = 'credentials'
        user, password = get_credentials()
        stage = 'request_write'
        sock.settimeout(tcp_timeout)
        sock.sendall(request_bytes(config,mount,user,password))
        row['request_written_local'] = local_time()
        stage = 'response_header'
        wire = Wire(sock, time.monotonic()+header_timeout, connection_start)
        source = StatusReader(wire, row)
        body = NtripBody(source)
        row['headers_complete'] = True
        if row['source_table']:
            row['conclusion'] = 'SOURCETABLE'
            return row
        stage = 'body'
        wire.deadline = time.monotonic()+seconds
        body_start = time.monotonic()
        row['body_observation_limit_s'] = seconds
        while time.monotonic()<wire.deadline:
            data = body.read()
            if not data:
                row['stop_reason'] = 'EOF_OR_CHUNKED_END'
                break
            if row['first_body_s'] is None:
                row['first_body_s'] = time.monotonic()-connection_start
                row['first_body_after_success_s'] = time.monotonic()-body_start
            row['body_bytes'] += len(data)
            if row['body_bytes']==len(data) and data.startswith((b'SOURCETABLE ',b'STR;')):
                row['source_table'] = True
            previous = scanner.frames
            scanner.feed(data)
            if scanner.frames>previous:
                if row['first_valid_frame_s'] is None:
                    row['first_valid_frame_s'] = time.monotonic()-connection_start
                    row['first_valid_frame_local'] = local_time()
                row['last_valid_frame_local'] = local_time()
        row.setdefault('stop_reason','OBSERVATION_LIMIT')
    except Exception as exc:
        row['failure_stage'], row['error_type'] = stage, type(exc).__name__
        row['stop_reason'] = 'TIMEOUT' if isinstance(exc,TimeoutError) else 'ERROR'
        if row['source_table']:
            row['conclusion'] = 'SOURCETABLE'
        elif stage=='credentials':
            row['conclusion'] = 'CREDENTIALS_ERROR'
        elif stage=='tls':
            row['conclusion'] = 'TLS_ERROR'
        elif row['status'] and row['status']!='200':
            row['conclusion'] = 'HTTP_'+row['status']
        elif stage=='response_header':
            row['conclusion'] = 'HEADER_TIMEOUT' if isinstance(exc,TimeoutError) else 'HEADER_INVALID'
        elif stage!='body':
            row['conclusion'] = 'REQUEST_WRITE_FAILED'
    finally:
        if source is not None:
            source.close()
        if sock is not None:
            sock.close()
        row.update(scanner.summary())
        row['response_wire_bytes'] = wire.count if wire else 0
        if wire and wire.first_s is not None:
            row['first_response_s'] = wire.first_s
        if scanner.frames:
            row['conclusion'] = 'VALID_RTCM'
        elif row.get('conclusion') is None:
            row['conclusion'] = ('SOURCETABLE' if row['source_table'] else
                'BODY_NO_VALID_RTCM' if row['body_bytes'] else 'SUCCESS_NO_BODY')
        row['elapsed_s'], row['end_local'] = time.monotonic()-started, local_time()
    return row


def run_mounts(config, mounts, target, get_credentials, on_result=None, **kwargs):
    results = []
    entry_reachable = False
    for mount in mounts:
        row = probe(config,mount,target,get_credentials,**kwargs)
        results.append(row)
        if on_result:
            on_result(row)
        entry_reachable |= row['tcp_connected']
        if (not entry_reachable and not row['tcp_connected']) or row['conclusion']=='CREDENTIALS_ERROR':
            why = 'NOT_TESTED_CREDENTIALS' if row['conclusion']=='CREDENTIALS_ERROR' else 'NOT_TESTED'
            for rest in mounts[len(results):]:
                results.append(dict(mount=rest,target_ip=target,status=None,protocol=None,
                    first_valid_frame_s=None,body_bytes=0,valid_rtcm_frames=0,
                    message_types={},igs_subtypes={},conclusion=why,tested=False))
                if on_result:
                    on_result(results[-1])
            break
    return results


def route_info(target, bind_ip=None, bind_index=None):
    if sys.platform!='win32':
        return {'note':'Windows route inventory unavailable on this OS'}
    command = ("$OutputEncoding=[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); "
               f"Find-NetRoute -RemoteIPAddress '{target}'")
    if bind_index is not None:
        command += f' -InterfaceIndex {bind_index}'
    command += ' | Select-Object InterfaceAlias,InterfaceIndex,IPAddress,NextHop,DestinationPrefix | ConvertTo-Json -Compress'
    try:
        out = subprocess.check_output(['powershell','-NoProfile','-Command',command],
                                      stderr=subprocess.DEVNULL,timeout=10)
        return {'route':json.loads(out.decode('utf-8-sig')),'bind_ip':bind_ip}
    except Exception as exc:
        return {'inventory_error':type(exc).__name__}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root',type=Path,help='Project containing tools/ntrip_capture.py and config/; auto-detected by default')
    parser.add_argument('--config',type=Path,default=ROOT/'config/caster_whu.json')
    parser.add_argument('--mount',action='append',help='One mount, repeatable; default broadcast/orbit-clock/bias')
    parser.add_argument('--connect-ip',type=str,help='Explicit numeric peer IP; Host remains the configured hostname')
    parser.add_argument('--bind-ip',type=str,help='Explicit local source IP; Windows IPv4 also pins its interface')
    parser.add_argument('--credentials-file',type=Path,help='Existing local properties file; credentials never passed as args')
    parser.add_argument('--seconds',type=float,default=30,help='Body observation after success, >0 and <=30 seconds')
    parser.add_argument('--header-timeout', type=float, default=HEADER_TIMEOUT,
                        help='Wait for NTRIP admission, >0 and <=120 seconds')
    args = parser.parse_args(argv)
    output = ROOT/'validation'/('ntrip_mount_probe_'+datetime.now(BEIJING).strftime('%Y%m%d_%H%M%S_%f'))
    output.mkdir(parents=True,exist_ok=False)
    summary = {'start_local':local_time(),'timezone':'UTC+8','credential_storage':'NONE',
               'project_root':str(ROOT),
               'results':[],'output':str(output),'tcp_timeout_s':TCP_TIMEOUT,
               'header_timeout_s':args.header_timeout,'post_success_observation_s':args.seconds}
    try:
        if not 0<args.header_timeout<=120:
            raise ValueError('HEADER_TIMEOUT_INVALID')
        if not 0<args.seconds<=30:
            raise ValueError('OBSERVATION_LIMIT_INVALID')
        config = validate_config(json.loads(args.config.read_text(encoding='utf-8-sig')))
        mounts = args.mount or [config['broadcast_mount'],config['ssr_mount'],config['bias_mount']]
        if any(not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',m) for m in mounts):
            raise ValueError('MOUNT_INVALID')
        bind_ip = str(ipaddress.ip_address(args.bind_ip)) if args.bind_ip else None
        override = str(ipaddress.ip_address(args.connect_ip)) if args.connect_ip else None
        if bind_ip and override and ipaddress.ip_address(bind_ip).version!=ipaddress.ip_address(override).version:
            raise ValueError('ADDRESS_FAMILY_MISMATCH')
        family = socket.AF_INET6 if bind_ip and ':' in bind_ip else socket.AF_INET if bind_ip else socket.AF_UNSPEC
        # Preserve per-caster failure handling and authentication boundaries on split profiles.
        groups = {}
        for mount in mounts:
            endpoint, anonymous = endpoint_for_mount(config, mount)
            key = (endpoint['host'], endpoint['port'], endpoint['tls'], anonymous)
            groups.setdefault(key, []).append(mount)
        if override and len({key[:3] for key in groups}) > 1:
            raise ValueError('CONNECT_IP_REQUIRES_SINGLE_CASTER')
        bind_index = interface_for_bind(bind_ip)
        summary.update(bind_ip=bind_ip, mount_order=mounts, connect_ip_override=override)
        cached = []
        def get_credentials():
            if not cached:
                cached.append(credentials(args.credentials_file))
            return cached[0]
        def checkpoint(row):
            row['host'] = host
            summary['results'].append(row)
            (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print('已完成：'+row['mount']+'；'+LABELS.get(row['conclusion'],row['conclusion']),flush=True)
        print('北京时间：'+summary['start_local'],flush=True)
        print('工程目录：'+str(ROOT),flush=True)
        for (host, port, tls, anonymous), group in groups.items():
            dns = resolve(host,port,family)
            target = override or next(iter(dns['addresses']),None)
            route = dict(host=host,port=port,dns=dns,selected_target_ip=target)
            if target:
                route['path'] = route_info(target,bind_ip,bind_index)
                route['proxy_fake_ip_target'] = ipaddress.ip_address(target) in ipaddress.ip_network('198.18.0.0/15')
            if len(groups)==1:
                summary.update(route)
            else:
                summary.setdefault('endpoints',[]).append(route)
            print('连接目标：'+host+' '+str(target)+'；绑定 IP：'+str(bind_ip),flush=True)
            print('DNS：'+json.dumps(dns,ensure_ascii=False),flush=True)
            if target:
                print('本地路由：'+json.dumps(route['path'],ensure_ascii=False),flush=True)
            if route.get('proxy_fake_ip_target'):
                print('路径提示：目标属于代理常用 Fake-IP 网段；结果仅代表此代理路径。',flush=True)
            if target:
                run_mounts(dict(host=host,port=port,tls=tls),group,target,
                    (lambda: ('','')) if anonymous else get_credentials,on_result=checkpoint,
                    bind_ip=bind_ip,bind_index=bind_index,seconds=args.seconds,header_timeout=args.header_timeout)
            else:
                for i, mount in enumerate(group):
                    checkpoint(dict(mount=mount,status=None,protocol=None,first_valid_frame_s=None,
                        body_bytes=0,valid_rtcm_frames=0,message_types={},igs_subtypes={},
                        conclusion='DNS_FAILED' if i==0 else 'NOT_TESTED_DNS'))
        summary['credentials_loaded'] = bool(cached)
        print('挂载点 | HTTP/ICY | 首有效帧(s) | 正文字节 | CRC有效帧 | 消息类型 | 结论',flush=True)
        for row in summary['results']:
            label = LABELS.get(row['conclusion'],row['conclusion'])
            status = (str(row.get('protocol') or '')+' '+str(row.get('status') or '—')).strip()
            first = '—' if row['first_valid_frame_s'] is None else f"{row['first_valid_frame_s']:.3f}"
            print(f"{row['mount']} | {status} | {first} | {row['body_bytes']} | {row['valid_rtcm_frames']} | {row['message_types']} | {label}",flush=True)
            if row.get('tcp_connected'):
                print(f"  实际本地/远端 IP：{row['local_ip']} -> {row['remote_ip']}；IGS 子类型：{row['igs_subtypes']}",flush=True)
            elif row.get('local_ip'):
                print(f"  本地源 IP：{row['local_ip']}；未建立远端连接；TCP 尝试数：{len(row.get('tcp_attempts',[]))}",flush=True)
    except Exception as exc:
        # Never print arbitrary exception text, remote response or credential values.
        summary['setup_error_type'] = type(exc).__name__
        print('PROBE_SETUP_FAILED: '+type(exc).__name__,flush=True)
    summary['end_local'] = local_time()
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    routes = summary.get('endpoints', [summary] if summary.get('host') else [])
    lines=['# NTRIP 挂载点探测', '', f"北京时间：{summary['start_local']}", '']
    for route in routes:
        lines.append(f"目标：{route.get('selected_target_ip')}；域名：{route['host']}:{route['port']}。"
                     f"代理 Fake-IP 目标：{route.get('proxy_fake_ip_target','未核实')}。")
    lines += ['', '|挂载点|状态|首有效帧 s|正文 bytes|CRC 有效帧|消息类型|结论|',
           '|---|---|---|---:|---:|---|---|']
    for r in summary['results']:
        lines.append(f"|{r['mount']}|{r.get('protocol') or ''} {r.get('status') or '—'}|{r['first_valid_frame_s'] if r['first_valid_frame_s'] is not None else '—'}|{r['body_bytes']}|{r['valid_rtcm_frames']}|{r['message_types']}|{LABELS.get(r['conclusion'],r['conclusion'])}|")
    lines+=['','收到有效数据仅指至少一帧 CRC24Q 通过；HTTP 200 本身不等同于有效数据。',
            '未测试行的零值不表示曾发出请求。首有效帧耗时从成功连接那次 TCP 尝试发起计时。',
            '只探测当前指定路径，不进行 PPP 解算、三路并发或 GitHub 发布。']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('本地摘要：'+str(output/'summary.json'),flush=True)
    return 0 if summary['results'] and all(r['conclusion']=='VALID_RTCM' for r in summary['results']) else 2


if __name__=='__main__':
    raise SystemExit(main())
