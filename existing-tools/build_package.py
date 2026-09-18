from pathlib import Path
import hashlib, shutil, urllib.request, zipfile
root = Path(__file__).resolve().parent
out = root / "dist" / "Product-Editing-Starter"
out.mkdir(parents=True, exist_ok=True)
url = "https://github.com/Acly/krita-ai-diffusion/releases/download/v1.53.0/krita_ai_diffusion-1.53.0.zip"
target = out / "krita_ai_diffusion-1.53.0.zip"
urllib.request.urlretrieve(url, target)
assert hashlib.sha256(target.read_bytes()).hexdigest() == "05b4e4072faecbcfa441a8829c97492cfe35974c92e407d0197db4e78ec91cbe", "Plugin hash mismatch"
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
source = out / "krita-ai-diffusion-1.53.0-source.zip"
urllib.request.urlretrieve("https://github.com/Acly/krita-ai-diffusion/archive/refs/tags/v1.53.0.zip", source)
with zipfile.ZipFile(source) as z:
    assert z.testzip() is None
for name in ("START-HERE.html", "THIRD-PARTY-LICENSE.txt"):
    shutil.copy2(root / name, out / name)
shutil.copy2(root / "README.md", out / "使用说明.txt")
(out / "SHA256SUMS.txt").write_text("\n".join(hashlib.sha256(p.read_bytes()).hexdigest()+"  "+p.name for p in sorted(out.iterdir()) if p.is_file() and p.name != "SHA256SUMS.txt"), encoding="utf-8")
print("Verified official plugin and packaged documentation. GPU inference NOT tested.")
