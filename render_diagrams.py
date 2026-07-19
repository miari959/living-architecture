import os
import zlib
import requests


# ==========================================
# PUML TO PNG RENDERER
# ==========================================

def deflate_and_encode(puml_content):
    """Compresses PUML text for the URL (Deflate + Custom Base64)"""
    zlibbed_str = zlib.compress(puml_content.encode('utf-8'))
    compressed_string = zlibbed_str[2:-4]  # Strip header/checksum
    return encode64(compressed_string)


def encode64(data):
    """PlantUML's custom Base64 encoding scheme"""
    mapping = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
    res = ""
    for i in range(0, len(data), 3):
        b1 = data[i]
        b2 = data[i + 1] if i + 1 < len(data) else 0
        b3 = data[i + 2] if i + 2 < len(data) else 0

        c1 = b1 >> 2
        c2 = ((b1 & 0x3) << 4) | (b2 >> 4)
        c3 = ((b2 & 0xF) << 2) | (b3 >> 6)
        c4 = b3 & 0x3F

        if i + 1 >= len(data):
            c3 = c4 = 64
        elif i + 2 >= len(data):
            c4 = 64

        res += mapping[c1 & 0x3F] + mapping[c2 & 0x3F] + \
               (mapping[c3 & 0x3F] if c3 != 64 else "") + \
               (mapping[c4 & 0x3F] if c4 != 64 else "")
    return res


def render_file(filepath):
    print(f"Processing: {filepath}...")
    with open(filepath, 'r') as f:
        content = f.read()

    # 1. Encode
    encoded = deflate_and_encode(content)
    url = f"https://www.plantuml.com/plantuml/png/{encoded}"

    # 2. Download
    try:
        response = requests.get(url)
        if response.status_code == 200:
            output_path = filepath.replace(".puml", ".png")
            with open(output_path, 'wb') as f:
                f.write(response.content)
            print(f"   -> Saved Image: {output_path}")
        else:
            print(f"   -> Error from Server: {response.status_code}")
    except Exception as e:
        print(f"   -> Download failed: {e}")


if __name__ == "__main__":
    output_dir = os.path.join(os.getcwd(), "output")
    files = [f for f in os.listdir(output_dir) if f.endswith(".puml")]

    print(f"Found {len(files)} diagrams to render.")
    for f in files:
        render_file(os.path.join(output_dir, f))