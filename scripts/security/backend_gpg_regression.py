"""Reproduce truncated-cleartext acceptance with ephemeral offline test keys."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--parent', action='store_true')
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='lms-gpg-regression-') as directory:
    os.chmod(directory, 0o700)
    env = {**os.environ, 'GNUPGHOME': directory}
    def run(options, data=None):
        return subprocess.run(['gpg', '--batch', '--pinentry-mode', 'loopback', '--passphrase', '',
                               *options], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env=env, timeout=30)
    try:
        key = run(['--quick-generate-key', 'LMS synthetic regression <test@example.invalid>',
                   'ed25519', 'sign', '1d'])
        assert key.returncode == 0, key.stderr.decode(errors='replace')
        keyring = Path(directory, 'trustedkeys.gpg')
        exported = run(['--export'])
        assert exported.returncode == 0 and exported.stdout
        keyring.write_bytes(exported.stdout)
        def verify_both(data):
            return [run(['--status-fd', '1', '--verify'], data),
                    subprocess.run(['gpgv', '--homedir', directory, '--keyring', str(keyring),
                                    '--status-fd', '1'], input=data, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, env=env, timeout=30)]
        normal = run(['--armor', '--clearsign'], b'Ordinary signed LMS test message\n')
        assert normal.returncode == 0
        assert run(['--verify'], normal.stdout).returncode == 0
        assert all(r.returncode == 0 for r in verify_both(normal.stdout))
        payload = b'Signed payload\r\f\n'
        signed = run(['--armor', '--clearsign'], payload)
        assert signed.returncode == 0
        assert run(['--verify'], signed.stdout).returncode == 0
        assert all(r.returncode == 0 for r in verify_both(signed.stdout))
        prefix, signature = signed.stdout.split(b'-----BEGIN PGP SIGNATURE-----', 1)
        header = prefix.split(b'\n\n', 1)[0] + b'\n\n'
        forged_results = []
        for width in [19997, 19998, 19999, 20000, 20001, 20002]:
            line = b'Signed payload' + b'\r' * (width - len(b'Signed payload'))
            forged = header + line + b'\fUnsigned payload\n-----BEGIN PGP SIGNATURE-----' + signature
            for verifier, result in zip(['gpg', 'gpgv'], verify_both(forged)):
                valid = b'[GNUPG:] VALIDSIG ' in result.stdout
                forged_results.append(dict(verifier=verifier, width=width,
                                          exit_code=result.returncode, valid_signature=valid))
                if not args.parent:
                    assert result.returncode != 0 and not valid, forged_results[-1]
        if args.parent:
            assert any(r['valid_signature'] for r in forged_results), 'Parent did not reproduce signature acceptance'
        binary = b'Binary\x00signed\xffpayload\n'
        detached = run(['--armor', '--detach-sign'], binary)
        assert detached.returncode == 0
        Path(directory, 'data').write_bytes(binary)
        Path(directory, 'signature').write_bytes(detached.stdout)
        assert run(['--verify', str(Path(directory, 'signature')), str(Path(directory, 'data'))]).returncode == 0
        print(json.dumps(dict(mode='parent' if args.parent else 'patched', normal_cleartext='PASS',
            formfeed_cleartext='PASS', binary_detached='PASS', forged=forged_results), indent=2))
    finally:
        subprocess.run(['gpgconf', '--kill', 'all'], env=env, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=10)
