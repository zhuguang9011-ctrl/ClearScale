import hashlib, pathlib, json
root = pathlib.Path("split-output")
root.mkdir(exist_ok=True)
source = pathlib.Path("full.zip")
expected = "34c041df6204dcb90dca6429043e985b7334f381b99b7894a31230cee4e3ac5d"
whole = hashlib.sha256()
manifest = []
with source.open("rb") as f:
    index = 1
    while True:
        first = f.read(8*1024*1024)
        if not first:
            break
        path = root / f"Product-Editor-Full.zip.{index:03}"
        digest = hashlib.sha256()
        size = 0
        with path.open("wb") as out:
            chunk = first
            while chunk:
                out.write(chunk)
                digest.update(chunk)
                whole.update(chunk)
                size += len(chunk)
                if size == 1024**3:
                    break
                chunk = f.read(min(8*1024*1024, 1024**3-size))
        manifest.append({"name": path.name, "bytes": size, "sha256": digest.hexdigest()})
        index += 1
assert whole.hexdigest() == expected, "Original artifact checksum mismatch"
# Re-read all split files to verify the actual bytes written.
verified = hashlib.sha256()
for entry in manifest:
    h = hashlib.sha256()
    with (root / entry["name"]).open("rb") as f:
        while chunk := f.read(8*1024*1024):
            h.update(chunk)
            verified.update(chunk)
    assert h.hexdigest() == entry["sha256"]
assert verified.hexdigest() == expected
(root / "SHA256SUMS.txt").write_text("".join(x["sha256"]+"  "+x["name"]+"\n" for x in manifest), encoding="utf-8")
(root / "manifest.json").write_text(json.dumps({"original_sha256": expected, "parts": manifest}, indent=2), encoding="utf-8")
(root / "READ-ME.txt").write_text(
"完整版分卷下载说明\n"
"所有 Product-Editor-Full.zip.001、.002 等分卷都必须下载，放在同一个文件夹，保留原名。\n"
"使用 7-Zip 打开 .001，点击提取。不要逐个解压，不要改扩展名。\n"
"提取到独立文件夹，例如 E:\\Product-Editor，然后双击 START.cmd。\n"
"请准备至少 50GB 可用空间。失败只需重下对应分卷。\n"
"这是原18.2GB完整包的字节分卷，没有删减模型或组件。\n"
"原包已验证Windows CPU后端启动；尚未验证GPU出图和Krita界面。\n"
"7-Zip官方网站：https://www.7-zip.org/\n",
encoding="utf-8-sig")
source.unlink()
print(f"Verified {len(manifest)} parts against original SHA256")
