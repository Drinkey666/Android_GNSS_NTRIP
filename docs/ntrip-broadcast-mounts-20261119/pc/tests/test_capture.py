import csv
import io
import json
import socket
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from ntrip_capture import ROOT, WHU_SSR_PROFILES, NtripBody, ProtocolError, RtcmScanner, crc24, record, validate_config
from replay_session import validate_capture, plan
from evaluate_solution import enu, evaluate

BASE=dict(host='localhost',port=2101,tls=False,ssr_mount='TEST_SSR',broadcast_mount='TEST_NAV',
          orbit_reference='APC',reference_pairs={'GPS':['1W','2W'],'GAL':['1C','5Q'],'BDS':['2I','6I']})


def frame(typ=1060):
    body=bytes([typ>>4,(typ&15)<<4,0,1])
    b=b'\xd3'+len(body).to_bytes(2,'big')+body
    return b+crc24(b).to_bytes(3,'big')


def parse(data):
    p=NtripBody(io.BufferedReader(io.BytesIO(data)))
    out=bytearray()
    while True:
        b=p.read()
        if not b:return bytes(out)
        out.extend(b)


class CaptureTests(unittest.TestCase):
    def test_whu_profile_cannot_silently_bind_other_mounts_or_apc(self):
        for profile in WHU_SSR_PROFILES:
            with self.subTest(profile=profile):
                with self.assertRaisesRegex(ValueError,'WHU_PROFILE_ENDPOINT_OR_DATUM_INVALID'):
                    validate_config(dict(BASE,ssr_profile=profile))
                c=dict(BASE,ssr_mount='SSRC00WHU0',bias_mount='OSBC00WHU1',orbit_reference='COM',ssr_profile=profile)
                self.assertEqual(validate_config(c),c)
                with self.assertRaisesRegex(ValueError,'WHU_PROFILE_ENDPOINT_OR_DATUM_INVALID'):
                    validate_config(dict(c,orbit_reference='APC'))

    @classmethod
    def setUpClass(cls):
        cls.root=ROOT/'validation'/('python_'+str(time.time_ns()))
        cls.root.mkdir()

    def test_http_binary(self):
        self.assertEqual(parse(b'HTTP/1.1 200 OK\r\nContent-Type: gnss/data\r\n\r\n'+frame()),frame())

    def test_icy(self):
        for h in (b'ICY 200 OK\r\n',b'ICY 200 OK\r\n\r\n',b'ICY 200 OK\r\nServer: x\r\n\r\n'):
            self.assertEqual(parse(h+frame()),frame())

    def test_chunked_binary_split(self):
        b=frame();chunks=b'3;f=x\r\n'+b[:3]+b'\r\n7\r\n'+b[3:]+b'\r\n0\r\nX: y\r\n\r\n'
        self.assertEqual(parse(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n'+chunks),b)

    def test_bad_status_text_redirect_encoding(self):
        for response in (b'HTTP/1.1 401 Unauthorized\r\n',b'HTTP/1.1 302 Redirect\r\n',b'SOURCETABLE 200 OK\r\n',
                         b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n',
                         b'HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\n\r\n'):
            with self.assertRaises(ProtocolError):parse(response)

    def test_bounds_and_truncation(self):
        for body in (b'zz\r\n',b'fffffffe\r\n',b'9\r\na'):
            with self.assertRaises(ProtocolError):parse(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n'+body)
        with self.assertRaises(ProtocolError):parse(b'HTTP/1.1 200 OK\r\nX: '+b'x'*5000+b'\r\n\r\n')

    def test_config_and_header_injection(self):
        validate_config(BASE)
        for change in (dict(host='http://localhost'),dict(port=0),dict(ssr_mount='a\r\nHeader:b'),
                       dict(broadcast_mount='TEST_SSR'),dict(password='not-allowed'),dict(orbit_reference='UNKNOWN')):
            with self.assertRaises(ValueError):validate_config(dict(BASE,**change))

    def test_crc_and_partial_reconnect(self):
        scanner=RtcmScanner();b=frame()
        scanner.feed(b[:4]);self.assertEqual(scanner.frames,0)
        scanner.feed(b[4:]);self.assertEqual(scanner.frames,1)
        bad=bytearray(b);bad[-1]^=1;scanner.feed(bad+b)
        self.assertEqual(scanner.frames,2);self.assertEqual(scanner.crc_errors,1)
        scanner.feed(b[:4]);scanner.reset();scanner.feed(b[4:])
        self.assertEqual(scanner.frames,2)

    def fake_capture(self,name,unauthorized=False,three=False):
        server=socket.socket();server.bind(('127.0.0.1',0));server.listen(8);server.settimeout(3)
        end=threading.Event();errors=[];workers=[]
        def serve(client):
            try:
                with client:
                    client.settimeout(2);source=client.makefile('rb')
                    status=source.readline()
                    while source.readline() not in (b'\r\n',b''):
                        pass
                    if unauthorized:
                        client.sendall(b'HTTP/1.1 401 Unauthorized\r\n\r\n');return
                    typ=1019 if b'TEST_NAV' in status else 1060
                    b=frame(typ)
                    client.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: gnss/data\r\nTransfer-Encoding: chunked\r\n\r\n')
                    client.sendall(b'3\r\n'+b[:3]+b'\r\n7\r\n'+b[3:]+b'\r\n')
                    end.wait(2)
            except Exception as exc:errors.append(type(exc).__name__)
        def accept():
            try:
                for _ in range(3 if three else 2):
                    client,_=server.accept();t=threading.Thread(target=serve,args=(client,),daemon=True);workers.append(t);t.start()
            except socket.timeout:
                pass
        t=threading.Thread(target=accept,daemon=True);t.start()
        directory=self.root/name
        try:
            config=dict(BASE,port=server.getsockname()[1])
            if three:config['bias_mount']='TEST_BIAS'
            m=record(config,directory,.35,1,'test-user','TEST_SECRET_NOT_A_PASSWORD')
        finally:
            end.set();t.join(4)
            for w in workers:w.join(3)
            server.close()
        self.assertFalse(errors)
        return directory,m

    def test_anonymous_broadcast_uses_its_own_socket_and_no_account(self):
        import socketserver
        observed = []
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                first = self.rfile.readline().split()
                headers = []
                while line := self.rfile.readline():
                    if line == b'\r\n':
                        break
                    headers.append(line.lower())
                observed.append((self.server.server_address[1],first[1],
                                 any(h.startswith(b'authorization:') for h in headers)))
                typ = 1019 if first[1] == b'/TEST_NAV' else 1060
                self.wfile.write(b'HTTP/1.1 200 OK\r\n\r\n' + frame(typ))
        with socketserver.ThreadingTCPServer(('127.0.0.1', 0), Handler) as main, \
                socketserver.ThreadingTCPServer(('127.0.0.1', 0), Handler) as nav:
            servers = [main, nav]
            for server in servers:
                threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                main_port, nav_port = [s.server_address[1] for s in servers]
                cfg = dict(BASE, port=main_port, bias_mount='TEST_BIAS',
                           anonymous_broadcast_endpoint=dict(host='127.0.0.1', port=nav_port, tls=False))
                manifest = record(cfg, self.root/'split_casters', .4, 1, 'demo', 'demo')
                self.assertTrue(manifest['transport_received_both'])
                self.assertEqual(set(observed), {(main_port,b'/TEST_SSR',True),
                    (main_port,b'/TEST_BIAS',True),(nav_port,b'/TEST_NAV',False)})
                with self.assertRaises(ValueError):
                    validate_config(dict(cfg, anonymous_broadcast_endpoint=dict(cfg['anonymous_broadcast_endpoint'], user='demo')))
            finally:
                for server in servers:
                    server.shutdown()

    def test_independent_bias_is_recorded_as_third_channel(self):
        directory,m=self.fake_capture('three_stream',three=True)
        self.assertEqual(m['format'],'PPP_NTRIP_CAPTURE_V2')
        self.assertTrue(m['transport_received_both'])
        self.assertEqual([s['valid_rtcm_frames'] for s in m['streams']],[1,1,1])
        self.assertEqual((directory/'bias.rtcm3').read_bytes(),frame(1060))
        self.assertIn('bias.rtcm3',m['files'])
        validate_capture(directory)

    def test_actual_two_stream_capture_integrity_and_no_secret(self):
        directory,m=self.fake_capture('record')
        self.assertTrue(m['transport_received_both'])
        self.assertEqual([x['valid_rtcm_frames'] for x in m['streams']],[1,1])
        self.assertFalse(m['ppp_ready'])
        validate_capture(directory)
        for p in directory.iterdir():
            self.assertNotIn(b'TEST_SECRET_NOT_A_PASSWORD',p.read_bytes())
            self.assertNotIn(b'Authorization:',p.read_bytes())
        with (directory/'arrivals.csv').open() as f:rows=list(csv.DictReader(f))
        self.assertEqual([int(x['seq']) for x in rows],list(range(len(rows))))
        self.assertEqual([int(x['utc_ns']) for x in rows],sorted(int(x['utc_ns']) for x in rows))
        with self.assertRaises(FileExistsError):record(BASE,directory,.1,1,'','')

    def test_401_no_retry_and_no_fake_data(self):
        directory,m=self.fake_capture('unauthorized',True)
        self.assertFalse(m['transport_received_both'])
        self.assertTrue(any(x['reason']=='HTTP_401' for x in m['failures']))
        self.assertEqual(m['total_bytes'],0)
        with self.assertRaises(ValueError):validate_capture(directory)

    def test_hash_tamper_is_rejected(self):
        directory,m=self.fake_capture('tamper')
        with (directory/'ssr.rtcm3').open('ab') as f:f.write(b'x')
        with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):validate_capture(directory)

    def test_native_txt_preflight_and_replay_plan_time_gate(self):
        directory,m=self.fake_capture('prepare')
        unix_ns=(m['start_utc_ns']+m['end_utc_ns'])//2
        gps_ns=unix_ns-315964800000000000+18000000000
        cols=['']*37;cols[0]='Raw';cols[2]='1000000000';cols[5]=str(1000000000-gps_ns)
        cols[6]='0';cols[10]='0';cols[11]='1';cols[12]='0';cols[13]='9'
        cols[14]=str(gps_ns%604800000000000-75000000);cols[15]='10';cols[16]='40'
        cols[17]='0';cols[18]='.1';cols[19]='1';cols[20]='22000000';cols[21]='.1'
        cols[22]='1575420000';cols[28]='1';cols[35]='C'
        txt=directory/'test_raw.txt';txt.write_text(','.join(cols)+'\n',encoding='ascii')
        probe=subprocess.run([str(ROOT/'bin/ppp_ssr_replay.exe'),'--scan-txt',str(txt)],capture_output=True)
        self.assertEqual(probe.returncode,0,probe.stderr)
        span=json.loads(probe.stdout);self.assertEqual(span['epochs'],1)
        self.assertLess(abs(span['first_utc_ns']-unix_ns),10)
        products={}
        for key in ('ionex','vmf_first','vmf_second','orography','atx'):
            p=directory/(key+'.fixture');p.write_text('NOT_A_REAL_PRODUCT; preflight plan only',encoding='ascii');products[key]=str(p)
        config=dict(capture=str(directory),txt=str(txt),products=products)
        p=plan(config,self.root/'planned')
        self.assertIn('SSR_CODE_BIAS_NOT_SEEN',p['warnings'][0]);self.assertEqual(p['status'],'PREPARED')
        self.assertTrue(p['phase_osb'])
        self.assertEqual(p['command'][p['command'].index('--ssr-phase-osb')+1],'on')
        disabled=plan(dict(config,phase_osb=False),self.root/'phase_disabled')
        self.assertFalse(disabled['phase_osb'])
        self.assertEqual(disabled['command'][disabled['command'].index('--ssr-phase-osb')+1],'off')
        with self.assertRaisesRegex(ValueError,'PHASE_OSB_MUST_BE_BOOLEAN'):
            plan(dict(config,phase_osb=1),self.root/'bad_phase_switch')
        cols[5]=str(1000000000-(gps_ns-86400000000000));txt.write_text(','.join(cols)+'\n',encoding='ascii')
        with self.assertRaisesRegex(ValueError,'TXT_OUTSIDE_CAPTURE_TIME'):plan(config,self.root/'wrong_time')

    def test_enu_known_axes_and_normal_height(self):
        ref=dict(frame='WGS84',source='synthetic known coordinate',lat_deg=0,lon_deg=0,height_m=0,height_type='ELLIPSOID')
        self.assertEqual(enu((6378138,2,3),ref),(2,3,1))
        ref.update(height_type='NORMAL',height_m=459)
        self.assertEqual(enu((6378138,2,3),ref),(2,3,None))
        with self.assertRaises(ValueError):enu((1,2,3),dict(ref,frame='UNKNOWN'))

    def test_no_convergence_across_missing_solution(self):
        p=self.root/'solution.csv'
        with p.open('w',newline='',encoding='ascii') as f:
            w=csv.writer(f);w.writerow(['week','tow','Q','x_m','y_m','z_m'])
            for i in range(81):w.writerow([2400,100+i,0 if i==40 else 6,6378137,.5,0])
        ref=dict(frame='WGS84',source='synthetic test',lat_deg=0,lon_deg=0,height_m=0,height_type='ELLIPSOID')
        summary=evaluate(p,ref,self.root/'errors')
        self.assertEqual(summary['ppp_epochs'],80)
        self.assertIsNone(summary['horizontal_convergence_start_s'])
        self.assertAlmostEqual(summary['statistics']['horizontal_m']['rms'],.5)


if __name__=='__main__':unittest.main(verbosity=2)
