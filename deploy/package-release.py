"""Package application code and published, non-personal matching artifacts only."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', '.venv', '__pycache__', 'node_modules', '.next', '.DS_Store', '.pytest_cache'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    exported = subprocess.check_output(['uv', 'export', '--extra', 'local', '--no-dev', '--no-hashes', '--no-emit-project', '--no-header'], cwd=ROOT / 'backend', text=True)
    cpu = [line for line in exported.splitlines() if line and not line.lstrip().startswith('#') and not re.match(r'(torch|triton|nvidia-[^= ]+)==', line)]
    (ROOT / 'deploy/requirements-cpu.txt').write_text('\n'.join(cpu) + '\n')
    with tarfile.open(args.output, 'w:gz', dereference=True) as bundle:
        for folder in ['backend', 'web', 'scripts', 'supabase', 'deploy']:
            for path in sorted((ROOT / folder).rglob('*')):
                if not path.is_file() or any(part in EXCLUDED for part in path.relative_to(ROOT).parts): continue
                if path.name.startswith('.env') or path.suffix in {'.pem', '.key', '.pyc', '.tsbuildinfo'} or path.name == 'london-instance.json': continue
                bundle.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
        for folder in ['data/onboarding', 'data/prospects/cdbd25ac18bbcbf97ddf07d6']:
            bundle.add(ROOT / folder, arcname=folder)
        model = 'models--sentence-transformers--all-MiniLM-L6-v2'
        revision = '1110a243fdf4706b3f48f1d95db1a4f5529b4d41'
        cache = Path.home() / '.cache/huggingface/hub' / model
        bundle.add(cache / 'snapshots' / revision, arcname=f'model-cache/hub/{model}/snapshots/{revision}')
        if (cache / 'refs').exists():
            bundle.add(cache / 'refs', arcname=f'model-cache/hub/{model}/refs')
    print({'bytes': args.output.stat().st_size, 'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest()})


if __name__ == '__main__': main()
